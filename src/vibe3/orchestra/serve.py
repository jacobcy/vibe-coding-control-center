"""vibe3 serve command - HTTP + heartbeat server for GitHub webhook orchestration."""

import asyncio
import os
import signal
from concurrent.futures import ThreadPoolExecutor
from typing import Annotated

import typer
import uvicorn
from fastapi import FastAPI

from vibe3.clients.github_client import GitHubClient
from vibe3.observability.logger import setup_logging
from vibe3.orchestra.config import OrchestraConfig
from vibe3.orchestra.dispatcher import Dispatcher
from vibe3.orchestra.flow_orchestrator import FlowOrchestrator
from vibe3.orchestra.heartbeat import HeartbeatServer
from vibe3.orchestra.serve_utils import (
    _setup_tailscale_webhook,
    _start_async_serve,
    _validate_pid_file,
)
from vibe3.orchestra.services.assignee_dispatch import AssigneeDispatchService
from vibe3.orchestra.services.comment_reply import CommentReplyService
from vibe3.orchestra.services.pr_review_dispatch import PRReviewDispatchService
from vibe3.orchestra.webhook_handler import make_webhook_router

app = typer.Typer(
    help="Orchestra server: GitHub webhook receiver + heartbeat polling",
    no_args_is_help=True,
)


def _build_server(config: OrchestraConfig) -> tuple[HeartbeatServer, FastAPI]:
    """Instantiate heartbeat + FastAPI app with registered services."""
    heartbeat = HeartbeatServer(config)

    # Shared resources (reduces duplication)
    shared_executor = ThreadPoolExecutor(max_workers=config.max_concurrent_flows)
    shared_github = GitHubClient()
    shared_orchestrator = FlowOrchestrator(config)
    shared_dispatcher = Dispatcher(
        config,
        dry_run=config.dry_run,
        orchestrator=shared_orchestrator,
    )

    if config.assignee_dispatch.enabled:
        heartbeat.register(
            AssigneeDispatchService(
                config,
                dispatcher=shared_dispatcher,
                github=shared_github,
                executor=shared_executor,
            )
        )
    if config.comment_reply.enabled:
        heartbeat.register(
            CommentReplyService(
                config,
                github=shared_github,
            )
        )
    if config.pr_review_dispatch.enabled:
        heartbeat.register(
            PRReviewDispatchService(
                config,
                dispatcher=shared_dispatcher,
                executor=shared_executor,
            )
        )

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
    async_mode: Annotated[
        bool,
        typer.Option("--async", help="Run in tmux background session"),
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
        typer.Option("-v", "--verbose", count=True, help="Increase verbosity"),
    ] = 0,
) -> None:
    """Start Orchestra server (HTTP webhook receiver + heartbeat polling).

    Listens for GitHub webhook events on POST /webhook/github and
    dispatches manager agents based on issue assignee changes.

    Polling fallback runs every --interval seconds to catch any events
    missed by the webhook (e.g. during downtime).

    By default, port/repo come from config/settings.yaml:
    - orchestra.port
    - orchestra.repo (if unset, gh resolves current repository by working directory)

    Configure GitHub to send webhook events to:
        http://<your-server>:<port>/webhook/github

    Examples:
        vibe3 serve start
        vibe3 serve start --port 9000 --interval 900
        vibe3 serve start --repo owner/repo --dry-run
        vibe3 serve start --async --ts
    """
    setup_logging(verbose=verbose)

    config = OrchestraConfig.from_settings()
    if not config.enabled:
        typer.echo("Orchestra is disabled in config (orchestra.enabled=false)")
        raise typer.Exit(1)

    overrides: dict[str, object] = {}
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

    if async_mode:
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
