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
                "Default uses orchestra.polling_interval from config/settings.yaml"
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
                "Default uses orchestra.port from config/settings.yaml"
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

    Defaults from config/settings.yaml; repo defaults to current repository.
    """
    # Inherit global verbose if not specified locally
    if verbose == 0 and "verbose" in ctx.meta:
        verbose = ctx.meta["verbose"]

    setup_logging(verbose=verbose)

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

    gate = FailedGate(repo=config.repo)
    result = gate.check()
    if result.blocked:
        typer.echo("\nOrchestra start blocked by open state/failed issue\n")
        typer.echo(f"issue:  #{result.issue_number}")
        typer.echo(f"title:  {result.issue_title}")
        typer.echo(f"reason: {result.reason}")
        if result.comment_url:
            typer.echo(f"url:    {result.comment_url}")
        typer.echo(
            "\nResolve the failed issue manually, transition it back to state/handoff, "
            "then retry serve start."
        )
        raise typer.Exit(1)

    missing_backend_commands = find_missing_backend_commands(
        env_path=os.environ.get("PATH")
    )
    if missing_backend_commands:
        typer.echo("\nOrchestra start blocked by missing backend executables in PATH\n")
        for backend, command in missing_backend_commands.items():
            typer.echo(f"- {backend}: expected `{command}` in PATH")
        typer.echo(
            "\nFix the shell environment used to launch serve, or update "
            "`config/models.json` to use only installed backends, then retry."
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
    """Show Orchestra server status."""
    config = load_orchestra_config()
    pid, is_valid = _validate_pid_file(config.pid_file)

    if pid is None:
        if _orchestra_tmux_session_exists():
            typer.echo("Orchestra server running in tmux session (PID file missing)")
            raise typer.Exit(0)
        typer.echo("Orchestra server is not running (no PID file)")
        raise typer.Exit(0)

    if not is_valid:
        if _orchestra_tmux_session_exists():
            typer.echo(
                "Orchestra server running in tmux session "
                f"(stale PID file points to non-orchestra process {pid})"
            )
            raise typer.Exit(0)
        typer.echo(
            f"Orchestra server is not running (stale PID file, process {pid} "
            "is not orchestra)"
        )
        raise typer.Exit(0)

    typer.echo(f"Orchestra server running (PID: {pid})")


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
