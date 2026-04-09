"""vibe3 server - HTTP webhook receiver and CLI management."""

import asyncio
import hashlib
import hmac
import json
import os
import signal
import sys
from pathlib import Path
from typing import Annotated, Any

import typer
import uvicorn
from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from loguru import logger

from vibe3.clients.git_client import GitClient
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.observability.logger import setup_logging
from vibe3.orchestra.logging import orchestra_events_log_path, orchestra_log_dir
from vibe3.runtime.event_bus import GitHubEvent
from vibe3.runtime.heartbeat import HeartbeatServer
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

app = typer.Typer(
    help="Orchestra server: GitHub webhook receiver + heartbeat polling",
    no_args_is_help=True,
)


def _verify_signature(body: bytes, secret: str, header: str) -> bool:
    """Return True if the HMAC-SHA256 signature matches."""
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header)


def make_webhook_router(
    heartbeat: HeartbeatServer,
    webhook_secret: str | None,
) -> APIRouter:
    """Build a FastAPI router with GitHub webhook and health endpoints."""

    router = APIRouter()

    @router.post("/webhook/github")
    async def receive_webhook(
        request: Request,
        x_github_event: str = Header(...),
        x_hub_signature_256: str | None = Header(None),
        x_github_delivery: str | None = Header(None),
    ) -> JSONResponse:
        body = await request.body()

        if webhook_secret:
            if not x_hub_signature_256:
                raise HTTPException(status_code=401, detail="Missing webhook signature")
            if not _verify_signature(body, webhook_secret, x_hub_signature_256):
                raise HTTPException(status_code=403, detail="Invalid webhook signature")

        try:
            payload: dict[str, Any] = json.loads(body)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail=f"Invalid JSON: {exc}") from exc

        action = str(payload.get("action", ""))

        logger.bind(
            domain="orchestra",
            action="webhook",
            delivery=x_github_delivery,
        ).info(
            "Received: "
            f"{x_github_event}/{action} "
            f"(source=webhook, delivery={x_github_delivery or '-'})"
        )

        event = GitHubEvent(
            event_type=x_github_event,
            action=action,
            payload=payload,
            source="webhook",
        )
        await heartbeat.emit(event)

        return JSONResponse({"status": "accepted", "event": x_github_event})

    @router.get("/health")
    async def health() -> JSONResponse:
        return JSONResponse(
            {
                "status": "ok",
                "services": heartbeat.service_names,
                "queue_size": heartbeat.queue_size,
            }
        )

    @router.get("/heartbeat")
    async def heartbeat_status() -> JSONResponse:
        """Legacy heartbeat status (use /status for full orchestra snapshot)."""
        return JSONResponse(
            {
                "running": heartbeat.running,
                "services": heartbeat.service_names,
                "polling_interval": heartbeat.config.polling_interval,
                "polling_enabled": heartbeat.config.polling.enabled,
                "max_concurrent": heartbeat.config.max_concurrent_flows,
            }
        )

    return router


def _ensure_port_available(port: int) -> None:
    """Raise typer.Exit if port is already in use."""
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            # Use SO_REUSEADDR to be consistent with common server behavior
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(("0.0.0.0", port))
        except OSError as e:
            if e.errno in (48, 98):  # MacOS: 48, Linux: 98
                typer.echo(
                    f"\n[bold red]Error:[/] Port {port} is already in use.",
                    err=True,
                )
                typer.echo(
                    "Check if another Orchestra service is running on this port.",
                    err=True,
                )
                typer.echo(
                    "Use [bold]vibe3 serve stop[/] or specify [bold]--port[/].\n",
                    err=True,
                )
                raise typer.Exit(1)
            raise


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

    config = OrchestraConfig.from_settings()
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
    _ensure_port_available(config.port)

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
    config = OrchestraConfig.from_settings()
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
    config = OrchestraConfig.from_settings()
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
