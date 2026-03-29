"""vibe3 serve command - HTTP + heartbeat server for GitHub webhook orchestration."""

import asyncio
import os
import signal
from pathlib import Path
from typing import Annotated

import typer
import uvicorn
from fastapi import FastAPI

from vibe3.observability.logger import setup_logging
from vibe3.orchestra.config import OrchestraConfig
from vibe3.orchestra.heartbeat import HeartbeatServer
from vibe3.orchestra.services.assignee_dispatch import AssigneeDispatchService
from vibe3.orchestra.services.comment_reply import CommentReplyService
from vibe3.orchestra.webhook_handler import make_webhook_router

app = typer.Typer(
    help="Orchestra server: GitHub webhook receiver + heartbeat polling",
    no_args_is_help=True,
)


def _is_orchestra_process(pid: int) -> bool:
    """Check if a PID is actually an orchestra process."""
    import subprocess

    try:
        result = subprocess.run(
            ["ps", "-p", str(pid), "-o", "command="],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return False

        cmdline = result.stdout.strip().lower()
        return "vibe3" in cmdline and "serve" in cmdline
    except Exception:
        return False


def _validate_pid_file(pid_file: Path) -> tuple[int | None, bool]:
    """Validate PID file and check if process is running.

    Returns:
        Tuple of (pid, is_valid_orchestra_process)
    """
    if not pid_file.exists():
        return None, False

    try:
        pid = int(pid_file.read_text().strip())
    except ValueError:
        return None, False

    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return pid, False
    except PermissionError:
        return pid, False

    return pid, _is_orchestra_process(pid)


def _build_server(config: OrchestraConfig) -> tuple[HeartbeatServer, FastAPI]:
    """Instantiate heartbeat + FastAPI app with registered services."""
    heartbeat = HeartbeatServer(config)

    heartbeat.register(AssigneeDispatchService(config))
    if config.comment_reply.enabled:
        heartbeat.register(CommentReplyService(config))

    fastapi_app = FastAPI(title="vibe3 Orchestra", version="1.0")
    fastapi_app.include_router(make_webhook_router(heartbeat, config.webhook_secret))
    return heartbeat, fastapi_app


async def _run(config: OrchestraConfig, port: int) -> None:
    """Run heartbeat + HTTP server concurrently."""
    heartbeat, fastapi_app = _build_server(config)

    uv_config = uvicorn.Config(
        fastapi_app,
        host="0.0.0.0",
        port=port,
        log_level="warning",  # loguru handles our logs
    )
    uv_server = uvicorn.Server(uv_config)

    await asyncio.gather(
        heartbeat.run(),
        uv_server.serve(),
    )


@app.command()
def start(
    interval: Annotated[
        int,
        typer.Option(
            "--interval", "-i", help="Polling interval in seconds (fallback tick)"
        ),
    ] = 900,
    port: Annotated[
        int,
        typer.Option("--port", "-p", help="HTTP port for webhook receiver"),
    ] = 8080,
    repo: Annotated[
        str | None,
        typer.Option("--repo", "-r", help="GitHub repo (owner/repo)"),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Log actions without executing"),
    ] = False,
    verbose: Annotated[
        int,
        typer.Option("-v", "--verbose", count=True, help="Increase verbosity"),
    ] = 0,
) -> None:
    """Start Orchestra server (HTTP webhook receiver + heartbeat polling).

    Listens for GitHub webhook events on POST /webhook/github and
    dispatches manager agents based on issue assignee changes.

    Polling fallback runs every --interval seconds to catch any events
    missed by the webhook (e.g. during downtime).

    Configure GitHub to send webhook events to:
        http://<your-server>:<port>/webhook/github

    Examples:
        vibe3 serve start
        vibe3 serve start --port 9000 --interval 900
        vibe3 serve start --repo owner/repo --dry-run
    """
    setup_logging(verbose=verbose)

    config = OrchestraConfig.from_settings()
    if interval != 900:
        config = config.model_copy(update={"polling_interval": interval})
    if port != 8080:
        config = config.model_copy(update={"port": port})
    if repo is not None:
        config = config.model_copy(update={"repo": repo})
    if dry_run:
        config = config.model_copy(update={"dry_run": dry_run})

    # Check for existing process
    pid, is_valid = _validate_pid_file(config.pid_file)
    if is_valid:
        typer.echo(f"Orchestra server already running (PID: {pid})")
        raise typer.Exit(1)
    elif pid is not None:
        typer.echo(f"Cleaning up stale PID file (dead process {pid})")
        config.pid_file.unlink(missing_ok=True)

    typer.echo(
        f"Starting Orchestra server on port {config.port} "
        f"(tick interval: {config.polling_interval}s, "
        f"max_concurrent: {config.max_concurrent_flows})"
    )
    typer.echo(f"Webhook endpoint: POST http://0.0.0.0:{config.port}/webhook/github")
    typer.echo("Press Ctrl+C to stop")

    try:
        asyncio.run(_run(config, config.port))
    except KeyboardInterrupt:
        typer.echo("Orchestra server stopped")


@app.command()
def status() -> None:
    """Show Orchestra server status."""
    config = OrchestraConfig.from_settings()
    pid, is_valid = _validate_pid_file(config.pid_file)

    if pid is None:
        typer.echo("Orchestra server is not running (no PID file)")
        raise typer.Exit(0)

    if not is_valid:
        typer.echo(
            f"Orchestra server is not running (stale PID file, process {pid} "
            "is not orchestra)"
        )
        raise typer.Exit(0)

    typer.echo(f"Orchestra server running (PID: {pid})")


@app.command()
def stop() -> None:
    """Stop Orchestra server.

    Sends SIGTERM to the server process. Use 'vibe3 serve status' to verify.
    """
    config = OrchestraConfig.from_settings()
    pid_file = config.pid_file
    pid, is_valid = _validate_pid_file(pid_file)

    if pid is None:
        typer.echo("Orchestra server is not running (no PID file)")
        raise typer.Exit(0)

    if not is_valid:
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
