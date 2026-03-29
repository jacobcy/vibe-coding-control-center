"""vibe3 serve command - HTTP + heartbeat server for GitHub webhook orchestration."""

import asyncio
import os
import signal
import subprocess
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
from vibe3.orchestra.services.pr_review_dispatch import PRReviewDispatchService
from vibe3.orchestra.webhook_handler import make_webhook_router

app = typer.Typer(
    help="Orchestra server: GitHub webhook receiver + heartbeat polling",
    no_args_is_help=True,
)


def _resolve_tsu_script() -> Path | None:
    """Resolve scripts/tsu.sh path from current repo/worktree."""
    env_path = os.environ.get("VIBE3_TSU_SCRIPT")
    if env_path:
        candidate = Path(env_path).expanduser()
        if candidate.exists():
            return candidate

    cwd_candidate = (Path.cwd() / "scripts" / "tsu.sh").resolve()
    if cwd_candidate.exists():
        return cwd_candidate

    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if result.returncode == 0:
            root = Path(result.stdout.strip())
            candidate = root / "scripts" / "tsu.sh"
            if candidate.exists():
                return candidate
    except Exception:
        pass

    return None


def _setup_tailscale_webhook(port: int) -> tuple[bool, str]:
    """Enable temporary Tailscale Funnel webhook via scripts/tsu.sh."""
    tsu = _resolve_tsu_script()
    if tsu is None:
        return (
            False,
            "Cannot enable --ts: scripts/tsu.sh not found "
            "(set VIBE3_TSU_SCRIPT to override)",
        )

    try:
        # Best-effort start; command is idempotent when already running.
        subprocess.run(
            [str(tsu), "start"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except Exception:
        # Keep going; next command reports a concrete failure if unavailable.
        pass

    try:
        result = subprocess.run(
            [str(tsu), "serve", "webhook", str(port)],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except FileNotFoundError:
        return False, f"Cannot execute tsu script: {tsu}"
    except Exception as exc:
        return False, f"Tailscale webhook setup failed: {exc}"

    stdout = (result.stdout or "").strip()
    stderr = (result.stderr or "").strip()
    if result.returncode != 0:
        detail = stderr or stdout or f"exit={result.returncode}"
        return False, f"Tailscale webhook setup failed: {detail}"

    return True, stdout or f"Tailscale webhook configured for port {port}"


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
    except (ValueError, OSError):
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

    if config.assignee_dispatch.enabled:
        heartbeat.register(AssigneeDispatchService(config))
    if config.comment_reply.enabled:
        heartbeat.register(CommentReplyService(config))
    if config.pr_review_dispatch.enabled:
        heartbeat.register(PRReviewDispatchService(config))

    fastapi_app = FastAPI(title="vibe3 Orchestra", version="1.0")
    fastapi_app.include_router(make_webhook_router(heartbeat, config.webhook_secret))
    return heartbeat, fastapi_app


def _build_async_serve_command(config: OrchestraConfig, verbose: int) -> list[str]:
    """Build self-invocation command for async tmux startup."""
    cmd = [
        "uv",
        "run",
        "python",
        "src/vibe3/cli.py",
        "serve",
        "start",
        "--interval",
        str(config.polling_interval),
        "--port",
        str(config.port),
    ]
    if config.repo:
        cmd.extend(["--repo", config.repo])
    if config.dry_run:
        cmd.append("--dry-run")
    for _ in range(verbose):
        cmd.append("-v")
    return cmd


def _start_async_serve(config: OrchestraConfig, verbose: int) -> tuple[bool, str]:
    """Start serve command in tmux session.

    Returns:
        (success, message)
    """
    session_name = "vibe3-orchestra-serve"
    cmd = _build_async_serve_command(config, verbose)
    try:
        subprocess.run(
            ["tmux", "new-session", "-d", "-s", session_name, "--"] + cmd,
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return False, "tmux not found, cannot start --async serve mode"
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        if "duplicate session" in stderr.lower():
            return (
                False,
                f"Async serve session already exists: {session_name} "
                "(use `tmux ls` / `tmux kill-session -t vibe3-orchestra-serve`)",
            )
        return False, f"Failed to start async serve: {stderr or str(exc)}"

    return (
        True,
        f"Started Orchestra server in tmux session: {session_name}\n"
        "Use `vibe3 serve status` or `tmux attach -t vibe3-orchestra-serve` to inspect",
    )


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
            "--interval",
            "-i",
            help=(
                "Polling interval override in seconds. "
                "Default uses orchestra.polling_interval from config/settings.yaml"
            ),
        ),
    ] = 900,
    port: Annotated[
        int,
        typer.Option(
            "--port",
            "-p",
            help=(
                "Webhook receiver port override. "
                "Default uses orchestra.port from config/settings.yaml"
            ),
        ),
    ] = 8080,
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
