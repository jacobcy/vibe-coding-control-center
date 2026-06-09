"""vibe3 server - HTTP server for orchestra status and CLI management."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rich.console import Console

import asyncio
import os
import signal
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Annotated

import typer
import uvicorn

from vibe3.clients import GitClient
from vibe3.config import find_missing_backend_commands, load_orchestra_config
from vibe3.models import OrchestraConfig
from vibe3.observability import (
    orchestra_events_log_path,
    orchestra_log_dir,
    setup_logging,
)
from vibe3.runtime import OrchestraInstanceInfo, write_instance_info

from .registry import (
    _build_server_with_launch_cwd,
    _kill_orchestra_tmux_session,
    _orchestra_tmux_session_exists,
    _resolve_async_cli_override_root,
    _resolve_dispatcher_models_root,
    _resolve_orchestra_log_dir,
    _setup_tailscale_webhook,
    _start_async_serve,
    validate_pid_file,
)
from .server_utils import find_available_port

app = typer.Typer(
    help="Orchestra server: heartbeat polling + HTTP status endpoints",
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
                "HTTP server port override. "
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
                "public URL for current port (via Tailscale Funnel)"
            ),
        ),
    ] = False,
    verbose: Annotated[
        int,
        typer.Option(
            "-v", "--verbose", count=True, help="Increase verbosity (or use global -v)"
        ),
    ] = 1,
) -> None:
    """Start Orchestra server (heartbeat polling + HTTP status endpoints).

    Defaults from config/v3/settings.yaml; repo defaults to current repository.
    """
    # Inherit global verbose if not specified locally
    if verbose == 1 and "verbose" in ctx.meta:
        verbose = ctx.meta["verbose"]

    setup_logging(verbose=verbose)

    # Register EDA event handlers for orchestra event processing
    from vibe3.domain import register_event_handlers

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
    instance_info, is_valid = validate_pid_file(config.pid_file)
    if is_valid and instance_info is not None:
        typer.echo(f"Orchestra server already running (PID: {instance_info.pid})")
        raise typer.Exit(0)
    elif instance_info is not None:
        typer.echo(f"Cleaning up stale PID file (dead process {instance_info.pid})")
        config.pid_file.unlink(missing_ok=True)

    # Pre-flight: Check if port is available
    requested_port = config.port
    effective_port, was_auto_discovered = find_available_port(
        config.port, config.port_range_max
    )
    if was_auto_discovered:
        config = config.model_copy(update={"port": effective_port})

    # Phase 1: FailedGate Preflight
    from vibe3.domain import FailedGate

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
    from vibe3.roles import resolve_manager_token

    manager_token = resolve_manager_token(config)
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
        if was_auto_discovered:
            typer.echo(
                f"  Port auto-discovered: {effective_port}"
                f" (requested port {requested_port} was occupied)"
            )
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

    port_hint = (
        f" (auto-discovered, port {requested_port} was occupied)"
        if was_auto_discovered
        else ""
    )
    typer.echo(
        f"Starting Orchestra server on port {config.port}{port_hint} "
        f"(tick interval: {config.polling_interval}s, "
        f"max_concurrent: {config.max_concurrent_flows}, "
        f"scene_base: {config.scene_base_ref})"
    )
    typer.echo(f"Main log: {orchestra_events_log_path()}")
    typer.echo(f"Log dir: {orchestra_log_dir()}")
    typer.echo(f"Status endpoint: GET http://0.0.0.0:{config.port}/status")
    typer.echo("Press Ctrl+C to stop")

    # Write instance info to global PID file
    instance_info = OrchestraInstanceInfo(
        pid=os.getpid(),
        cwd=Path.cwd(),
        port=config.port,
        started_at=datetime.now(),
    )
    write_instance_info(config.pid_file, instance_info)

    try:
        os.environ["VIBE3_ORCHESTRA_EVENT_LOG"] = "1"
        os.environ["VIBE3_REPO_MODELS_ROOT"] = str(
            _resolve_dispatcher_models_root(config, Path.cwd())
        )
        async_cli_root = _resolve_async_cli_override_root(config, Path.cwd())
        if async_cli_root is None:
            os.environ.pop("VIBE3_ASYNC_CLI_PROJECT_ROOT", None)
        else:
            os.environ["VIBE3_ASYNC_CLI_PROJECT_ROOT"] = str(async_cli_root)
        os.environ["VIBE3_ASYNC_LOG_DIR"] = str(_resolve_orchestra_log_dir(Path.cwd()))
        # --no-async flag: propagate to all dispatched role agents
        # Only set when user explicitly requested --no-async (not in async wrapper)
        if no_async:
            os.environ["VIBE3_NO_ASYNC"] = "1"
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


def _display_active_jobs(console: Console) -> None:
    """Display active and recent jobs from the actor registry."""
    from rich.table import Table

    from vibe3.execution import JobMonitorService
    from vibe3.utils.time_format import format_age_aware_time

    service = JobMonitorService()
    snapshot = service.snapshot()

    console.print("[bold]Active Jobs:[/bold]")

    if not snapshot.active_jobs and not snapshot.recent_jobs:
        console.print("  No active jobs")
        console.print()
        return

    if snapshot.active_jobs:
        table = Table(title="Running / Queued", show_lines=True)
        table.add_column("Actor", style="cyan", width=20)
        table.add_column("Type", style="magenta", width=12)
        table.add_column("Status", style="green", width=8)
        table.add_column("Issue", style="yellow", width=10)
        table.add_column("Branch", style="white")
        table.add_column("Started", style="dim", width=12)

        for job in snapshot.active_jobs:
            started_display = (
                format_age_aware_time(job.started_at) if job.started_at else "-"
            )
            issue_display = f"#{job.issue_number}" if job.issue_number > 0 else "-"
            table.add_row(
                job.actor_id[:20],
                job.job_type.upper(),
                job.status.upper(),
                issue_display,
                job.branch,
                started_display,
            )
        console.print(table)

    if snapshot.recent_jobs:
        table = Table(title="Recent (last 30m)", show_lines=True)
        table.add_column("Actor", style="cyan", width=20)
        table.add_column("Type", style="magenta", width=12)
        table.add_column("Status", style="yellow", width=8)
        table.add_column("Issue", style="yellow", width=10)
        table.add_column("Branch", style="white")
        table.add_column("Completed", style="dim", width=12)

        for job in snapshot.recent_jobs:
            completed_display = (
                format_age_aware_time(job.completed_at) if job.completed_at else "-"
            )
            issue_display = f"#{job.issue_number}" if job.issue_number > 0 else "-"
            table.add_row(
                job.actor_id[:20],
                job.job_type.upper(),
                job.status.upper(),
                issue_display,
                job.branch,
                completed_display,
            )
        console.print(table)

    console.print(
        f"  Summary: {snapshot.running_count} running, "
        f"{snapshot.completed_count} completed, "
        f"{snapshot.failed_count} failed (last 30m)"
    )
    console.print()


@app.command()
def status() -> None:
    """Show Orchestra server status, FailedGate state, and recent activity."""
    from rich.console import Console

    from vibe3.services import ServeStatusService, get_manager_usernames

    console = Console()

    config = load_orchestra_config()
    instance_info, is_valid = validate_pid_file(config.pid_file)
    tmux_exists = _orchestra_tmux_session_exists()

    # Display instance info from PID file
    if instance_info is not None:
        console.print("[bold]Instance Info:[/bold]")
        console.print(f"  PID: {instance_info.pid}")
        console.print(f"  Directory: {instance_info.cwd}")
        console.print(f"  Port: {instance_info.port}")
        console.print(
            f"  Started: {instance_info.started_at.strftime('%Y-%m-%d %H:%M:%S')}"
        )
        console.print()

    # Display manager username
    manager_usernames = get_manager_usernames(config)
    if manager_usernames:
        console.print("[bold]Configuration:[/bold]")
        console.print(f"  Manager: {manager_usernames[0]}")
        console.print()

    # Extract PID for compatibility with ServeStatusService
    pid = instance_info.pid if instance_info is not None else None

    service = ServeStatusService(config)
    service.display_status(pid, is_valid, tmux_exists)

    # Display active jobs from actor registry
    _display_active_jobs(console)


@app.command()
def stop() -> None:
    """Stop Orchestra server via SIGTERM."""
    config = load_orchestra_config()
    pid_file = config.pid_file
    instance_info, is_valid = validate_pid_file(pid_file)

    if instance_info is None:
        if _orchestra_tmux_session_exists():
            if _kill_orchestra_tmux_session():
                typer.echo("Stopped Orchestra server tmux session")
                raise typer.Exit(0)
            typer.echo("Failed to stop Orchestra tmux session")
            raise typer.Exit(1)
        typer.echo("Orchestra server is not running (no PID file)")
        raise typer.Exit(0)

    pid = instance_info.pid

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
        pid_file.unlink(missing_ok=True)
        raise typer.Exit(0)

    try:
        os.kill(pid, signal.SIGTERM)
        pid_file.unlink(missing_ok=True)
        typer.echo(f"Stopped Orchestra server (PID: {pid})")
    except ProcessLookupError:
        typer.echo(f"Process {pid} not found, cleaning up PID file")
        pid_file.unlink(missing_ok=True)
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

    Note: Even if the gate is already OPEN, this command will clear
    error_log to ensure old errors don't trigger the gate again.
    """
    from rich.console import Console

    from vibe3.domain import FailedGate

    console = Console()
    failed_gate = FailedGate()

    # Check if gate is ACTIVE
    gate_status = failed_gate.get_status()

    # Always clear error_log, even if gate is already OPEN
    # This prevents stale errors from re-triggering the gate
    if gate_status.is_active:
        # Gate is ACTIVE: show blocking info
        console.print("[cyan]Clearing Failed Gate[/cyan]")
        console.print(f"  - Reason: {gate_status.reason}")
        console.print(f"  - Blocked ticks: {gate_status.blocked_ticks}")
    else:
        # Gate is OPEN: inform user but still clear errors
        console.print("[yellow]Failed Gate is already OPEN[/yellow]")
        console.print("[cyan]Clearing error_log to prevent re-triggering[/cyan]")

    cleared_by = "admin:manual"
    failed_gate.clear(cleared_by, reason)

    console.print("\n[green]✓ Failed Gate cleared[/green]")
    console.print(f"  - Cleared by: {cleared_by}")
    console.print(f"  - Clear reason: {reason}")
    console.print("\nOrchestra will resume on next tick")


@app.command()
def logs(
    follow: Annotated[
        bool,
        typer.Option("-f", "--follow", help="Follow log output (tail -f)"),
    ] = False,
    lines: Annotated[
        int,
        typer.Option("-n", "--lines", help="Number of lines to show (default: 50)"),
    ] = 50,
) -> None:
    """Show Orchestra server logs.

    Displays recent log entries from the orchestra events log.
    Use -f to follow log output in real-time.
    """
    log_path = orchestra_events_log_path()

    if not log_path.exists():
        typer.echo(f"No log file found at {log_path}")
        typer.echo("Server may not have been started yet.")
        raise typer.Exit(1)

    try:
        if follow:
            subprocess.run(["tail", "-f", str(log_path)])
        else:
            subprocess.run(["tail", f"-n{lines}", str(log_path)])
    except KeyboardInterrupt:
        pass
