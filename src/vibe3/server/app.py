"""vibe3 server - HTTP webhook receiver and CLI management."""

import asyncio
import os
import signal
import sys
from pathlib import Path
from typing import Annotated

import typer
import uvicorn

from vibe3.agents.backends.codeagent_config import find_missing_backend_commands
from vibe3.clients.git_client import GitClient
from vibe3.config.orchestra_settings import load_orchestra_config
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.observability.logger import setup_logging
from vibe3.orchestra.logging import orchestra_events_log_path, orchestra_log_dir
from vibe3.server.registry import (
    _build_server_with_launch_cwd,
    _kill_orchestra_tmux_session,
    _orchestra_tmux_session_exists,
    _resolve_dispatcher_models_root,
    _resolve_orchestra_log_dir,
    _setup_tailscale_webhook,
    _start_async_serve,
    _validate_pid_file,
)
from vibe3.server.server_utils import ensure_port_available

app = typer.Typer(
    help="Orchestra server: GitHub webhook receiver + heartbeat polling",
    no_args_is_help=True,
)


# --- Server Run Logic ---


async def _run(config: OrchestraConfig, port: int) -> None:
    """Run heartbeat + HTTP server concurrently."""
    heartbeat, fastapi_app = _build_server_with_launch_cwd(config, Path.cwd())

    uv_config = uvicorn.Config(
        fastapi_app,
        host="0.0.0.0",
        port=port,
        log_level="warning",  # loguru handles our logs
    )
    uv_server = uvicorn.Server(uv_config)
    heartbeat_task = asyncio.create_task(heartbeat.run())
    server_task = asyncio.create_task(uv_server.serve())

    done, _pending = await asyncio.wait(
        {heartbeat_task, server_task},
        return_when=asyncio.FIRST_COMPLETED,
    )

    if heartbeat_task in done and not server_task.done():
        uv_server.should_exit = True
    if server_task in done and not heartbeat_task.done():
        heartbeat.stop()

    await asyncio.gather(heartbeat_task, server_task)


# --- CLI Commands ---


@app.command()
def start(
    ctx: typer.Context,
    interval: Annotated[
        int | None,
        typer.Option(
            "--interval",
            "-i",
            help=(
                "Polling interval override in seconds. "
                "Default uses orchestra.polling_interval from config/v3/settings.yaml"
            ),
        ),
    ] = None,
    port: Annotated[
        int | None,
        typer.Option(
            "--port",
            "-p",
            help=(
                "Webhook receiver port override. "
                "Default uses orchestra.port from config/v3/settings.yaml"
            ),
        ),
    ] = None,
    repo: Annotated[
        str | None,
        typer.Option(
            "--repo",
            "-r",
            help=(
                "GitHub repo override (owner/repo). "
                "Default uses orchestra.repo; if unset, uses current repository"
            ),
        ),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Log actions without executing"),
    ] = False,
    debug: Annotated[
        bool,
        typer.Option(
            "--debug",
            help=(
                "Debug mode: use current branch as auto scene base "
                "and 60s heartbeat by default"
            ),
        ),
    ] = False,
    no_async: Annotated[
        bool,
        typer.Option(
            "--no-async",
            help="Run synchronously (blocking) instead of async tmux session",
        ),
    ] = False,
    ts: Annotated[
        bool,
        typer.Option(
            "--ts",
            help=(
                "Temporary testing mode: auto-run scripts/tsu.sh to expose "
                "public webhook URL for current port"
            ),
        ),
    ] = False,
    verbose: Annotated[
        int,
        typer.Option(
            "-v", "--verbose", count=True, help="Increase verbosity (or use global -v)"
        ),
    ] = 0,
) -> None:
    """Start Orchestra server (webhook receiver + heartbeat polling).

    Defaults from config/v3/settings.yaml; repo defaults to current repository.
    """
    # Inherit global verbose if not specified locally
    if verbose == 0 and "verbose" in ctx.meta:
        verbose = ctx.meta["verbose"]

    setup_logging(verbose=verbose)

    # Register EDA event handlers for orchestra event processing
    from vibe3.domain.handlers import register_event_handlers

    register_event_handlers()

    # Orchestra events.log level follows global verbosity
    # Default: INFO (key runtime events for monitoring)
    # -v: already INFO (no change needed)
    # -vv: DEBUG (full debugging details)
    import os as _os

    if verbose >= 2:
        _os.environ["VIBE3_ORCHESTRA_LOG_LEVEL"] = "DEBUG"
    else:
        # Default and -v: show key events (tick completion, issue dispatch, etc.)
        _os.environ["VIBE3_ORCHESTRA_LOG_LEVEL"] = "INFO"

    config = load_orchestra_config()
    if not config.enabled:
        typer.echo("Orchestra is disabled in config (orchestra.enabled=false)")
        raise typer.Exit(1)

    overrides: dict[str, object] = {}
    effective_debug = debug or config.debug
    if effective_debug:
        current_branch = GitClient().get_current_branch()
        overrides["debug"] = True
        overrides["scene_base_ref"] = current_branch
        if interval is None:
            overrides["polling_interval"] = config.debug_polling_interval
    if interval is not None:
        overrides["polling_interval"] = interval
    if port is not None:
        overrides["port"] = port
    if repo is not None:
        overrides["repo"] = repo
    if dry_run:
        overrides["dry_run"] = dry_run
    if overrides:
        config = config.model_copy(update=overrides)

    # Check for existing process
    pid, is_valid = _validate_pid_file(config.pid_file)
    if is_valid:
        typer.echo(f"Orchestra server already running (PID: {pid})")
        raise typer.Exit(1)
    elif pid is not None:
        typer.echo(f"Cleaning up stale PID file (dead process {pid})")
        config.pid_file.unlink(missing_ok=True)

    # Pre-flight: Check if port is available
    ensure_port_available(config.port)

    # Phase 1: FailedGate Preflight
    from vibe3.orchestra.failed_gate import FailedGate

    gate = FailedGate()
    result = gate.check()
    if result.blocked:
        typer.echo("\nOrchestra start blocked by failed gate\n")
        typer.echo(f"reason: {result.reason}")
        typer.echo(f"blocked_ticks: {result.blocked_ticks}")
        typer.echo(
            "\nResolve the errors manually, then run "
            "'vibe3 serve resume --reason \"<reason>\"' "
            "to clear the failed gate and retry."
        )
        raise typer.Exit(1)

    # Warning: Manager token isolation
    from vibe3.roles.manager import _resolve_manager_token

    manager_token = _resolve_manager_token(config)
    if not manager_token:
        typer.echo(
            "\nWARNING: VIBE_MANAGER_GITHUB_TOKEN not configured.\n"
            "Manager role will use fallback token (same as human identity).\n"
            "Set VIBE_MANAGER_GITHUB_TOKEN in shell environment "
            "or config/keys.env to enable token isolation.\n"
        )

    missing_backend_commands = find_missing_backend_commands(
        env_path=os.environ.get("PATH")
    )
    if missing_backend_commands:
        typer.echo("\nOrchestra start blocked by missing backend executables in PATH\n")
        for backend, command in missing_backend_commands.items():
            typer.echo(f"- {backend}: expected `{command}` in PATH")
        typer.echo(
            "\nFix the shell environment used to launch serve, or update "
            "`config/v3/models.json` to use only installed backends, then retry."
        )
        raise typer.Exit(1)

    if not no_async:
        ok, msg = _start_async_serve(config, verbose)
        typer.echo(msg)
        if not ok:
            raise typer.Exit(1)
        if ts:
            ts_ok, ts_msg = _setup_tailscale_webhook(config.port)
            typer.echo(ts_msg)
            if not ts_ok:
                raise typer.Exit(1)
        raise typer.Exit(0)

    if ts:
        ts_ok, ts_msg = _setup_tailscale_webhook(config.port)
        typer.echo(ts_msg)
        if not ts_ok:
            raise typer.Exit(1)

    # Add visual separator for new server start
    separator_width = 60  # Standard width for readability
    typer.echo("")  # Blank line
    typer.echo("=" * separator_width)  # Separator line
    typer.echo("")  # Blank line

    typer.echo(
        f"Starting Orchestra server on port {config.port} "
        f"(tick interval: {config.polling_interval}s, "
        f"max_concurrent: {config.max_concurrent_flows}, "
        f"scene_base: {config.scene_base_ref})"
    )
    typer.echo(f"Main log: {orchestra_events_log_path()}")
    typer.echo(f"Log dir: {orchestra_log_dir()}")
    typer.echo(f"Webhook endpoint: POST http://0.0.0.0:{config.port}/webhook/github")
    typer.echo("Press Ctrl+C to stop")

    # Write PID file for the synchronous server process
    config.pid_file.parent.mkdir(parents=True, exist_ok=True)
    config.pid_file.write_text(str(os.getpid()))

    try:
        os.environ["VIBE3_ORCHESTRA_EVENT_LOG"] = "1"
        os.environ["VIBE3_REPO_MODELS_ROOT"] = str(
            _resolve_dispatcher_models_root(config, Path.cwd())
        )
        os.environ["VIBE3_ASYNC_LOG_DIR"] = str(_resolve_orchestra_log_dir(Path.cwd()))
        asyncio.run(_run(config, config.port))
    except KeyboardInterrupt:
        typer.echo("Orchestra server stopped")
    except SystemExit as e:
        # Catch uvicorn exit to avoid asyncio "never retrieved" warnings
        if e.code != 0:
            sys.exit(e.code)
        raise
    finally:
        # Cleanup PID file on exit
        if config.pid_file.exists():
            config.pid_file.unlink()


@app.command()
def status() -> None:
    """Show Orchestra server status and FailedGate state."""
    from rich.console import Console
    from rich.table import Table

    from vibe3.exceptions.error_tracking import ErrorTrackingService
    from vibe3.orchestra.failed_gate import FailedGate

    config = load_orchestra_config()
    pid, is_valid = _validate_pid_file(config.pid_file)
    console = Console()

    # Daemon status
    if pid is None:
        if _orchestra_tmux_session_exists():
            console.print("Orchestra server running in tmux session (PID file missing)")
            raise typer.Exit(0)
        console.print("Orchestra server is not running (no PID file)")
        raise typer.Exit(0)

    if not is_valid:
        if _orchestra_tmux_session_exists():
            console.print(
                "Orchestra server running in tmux session "
                f"(stale PID file points to non-orchestra process {pid})"
            )
            raise typer.Exit(0)
        console.print(
            f"Orchestra server is not running (stale PID file, process {pid} "
            "is not orchestra)"
        )
        raise typer.Exit(0)

    console.print(f"Orchestra server running (PID: {pid})\n")

    # FailedGate status
    failed_gate = FailedGate()
    gate_status = failed_gate.get_status()

    if gate_status.is_active:
        console.print("[red]Failed Gate: ACTIVE[/red]")
        console.print(f"  - Reason: {gate_status.reason}")
        if gate_status.triggered_at:
            console.print(f"  - Triggered at: {gate_status.triggered_at}")
        if gate_status.triggered_by_error_code:
            console.print(f"  - Error code: {gate_status.triggered_by_error_code}")
        console.print(f"  - Blocked ticks: {gate_status.blocked_ticks}")
        console.print(
            '\n[yellow]To resume:[/yellow] vibe3 serve resume --reason "<reason>"'
        )
    else:
        console.print("[green]Failed Gate: OPEN[/green]")

    # Error tracking status
    error_tracking = ErrorTrackingService.get_instance()
    error_status = error_tracking.get_status()

    if error_status["total_errors"] > 0:
        console.print("\nError Statistics:")
        console.print(f"  - Total errors: {error_status['total_errors']}")
        console.print(f"  - Model errors: {error_status['model_errors']}")
        console.print(f"  - API errors: {error_status['api_errors']}")
        console.print(f"  - Execution errors: {error_status['exec_errors']}")

        # Show recent errors
        recent_errors = error_tracking.get_recent_errors(limit=5)
        if recent_errors:
            table = Table(title="Recent Errors (last 5)", show_lines=True)
            table.add_column("Tick", style="cyan")
            table.add_column("Code", style="magenta")
            table.add_column("Message", style="white")

            for err in recent_errors:
                table.add_row(
                    str(err["tick_id"]),
                    err["error_code"],
                    err["error_message"][:80],  # Truncate long messages
                )

            console.print("\n")
            console.print(table)


@app.command()
def stop() -> None:
    """Stop Orchestra server via SIGTERM."""
    config = load_orchestra_config()
    pid_file = config.pid_file
    pid, is_valid = _validate_pid_file(pid_file)

    if pid is None:
        if _orchestra_tmux_session_exists():
            if _kill_orchestra_tmux_session():
                typer.echo("Stopped Orchestra server tmux session")
                raise typer.Exit(0)
            typer.echo("Failed to stop Orchestra tmux session")
            raise typer.Exit(1)
        typer.echo("Orchestra server is not running (no PID file)")
        raise typer.Exit(0)

    if not is_valid:
        if _orchestra_tmux_session_exists():
            if _kill_orchestra_tmux_session():
                pid_file.unlink(missing_ok=True)
                typer.echo(
                    "Stopped Orchestra server tmux session "
                    f"(stale PID file referenced process {pid})"
                )
                raise typer.Exit(0)
            typer.echo(
                "Failed to stop Orchestra tmux session "
                f"(stale PID file referenced process {pid})"
            )
            raise typer.Exit(1)
        typer.echo(f"Cleaning up stale PID file (process {pid} is not orchestra)")
        pid_file.unlink()
        raise typer.Exit(0)

    try:
        os.kill(pid, signal.SIGTERM)
        pid_file.unlink()
        typer.echo(f"Stopped Orchestra server (PID: {pid})")
    except ProcessLookupError:
        typer.echo(f"Process {pid} not found, cleaning up PID file")
        pid_file.unlink()
    except PermissionError:
        typer.echo(f"Permission denied to stop process {pid}")
        raise typer.Exit(1)


@app.command()
def resume(
    reason: Annotated[
        str,
        typer.Option(
            "--reason",
            "-r",
            help="Resume reason (required, will be logged)",
        ),
    ],
) -> None:
    """Clear FailedGate and allow orchestra to resume.

    This clears:
    - failed_gate_state table (reset gate to OPEN)
    - error_log table (clear all error records)

    The next tick will proceed normally after clearing.
    """
    from rich.console import Console

    from vibe3.orchestra.failed_gate import FailedGate

    console = Console()
    failed_gate = FailedGate()

    # Check if gate is ACTIVE
    gate_status = failed_gate.get_status()
    if not gate_status.is_active:
        console.print("[yellow]Failed Gate is already OPEN[/yellow]")
        console.print("No need to resume - orchestra is operating normally")
        raise typer.Exit(0)

    # Clear gate
    console.print("[cyan]Clearing Failed Gate[/cyan]")
    console.print(f"  - Reason: {gate_status.reason}")
    console.print(f"  - Blocked ticks: {gate_status.blocked_ticks}")

    cleared_by = "admin:manual"
    failed_gate.clear(cleared_by, reason)

    console.print("\n[green]✓ Failed Gate cleared[/green]")
    console.print(f"  - Cleared by: {cleared_by}")
    console.print(f"  - Clear reason: {reason}")
    console.print("\nOrchestra will resume on next tick")
