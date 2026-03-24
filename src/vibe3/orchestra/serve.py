"""vibe3 serve command - foreground server for GitHub label orchestration."""

import os
import signal
from pathlib import Path
from typing import Annotated

import typer
from loguru import logger

from vibe3.observability.logger import setup_logging
from vibe3.orchestra.config import OrchestraConfig
from vibe3.orchestra.poller import Poller

app = typer.Typer(
    help="Orchestra server for GitHub label-driven orchestration (runs in foreground)",
    no_args_is_help=True,
)


def _is_orchestra_process(pid: int) -> bool:
    """Check if a PID is actually an orchestra process.

    Args:
        pid: Process ID to check

    Returns:
        True if the process is orchestra, False otherwise
    """
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

    Args:
        pid_file: Path to PID file

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


@app.command()
def start(
    interval: Annotated[
        int, typer.Option("--interval", "-i", help="Polling interval in seconds")
    ] = 60,
    repo: Annotated[
        str | None, typer.Option("--repo", "-r", help="GitHub repo (owner/repo)")
    ] = None,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Only log actions, don't execute")
    ] = False,
    verbose: Annotated[
        int, typer.Option("-v", "--verbose", count=True, help="Increase verbosity")
    ] = 0,
) -> None:
    """Start Orchestra server (runs in foreground).

    This server monitors GitHub issues for state label changes and
    triggers corresponding commands (plan/run/review).

    NOTE: This runs in the foreground. For background execution,
    use nohup, tmux, or a process manager:

        # Using nohup
        nohup vibe3 serve start --interval 60 > orchestra.log 2>&1 &

        # Using tmux
        tmux new -d -s orchestra 'vibe3 serve start'

    Examples:
        vibe3 serve start
        vibe3 serve start --interval 30
        vibe3 serve start --repo owner/repo --dry-run
    """
    setup_logging(verbose=verbose)

    config = OrchestraConfig.from_settings()

    if interval != 60:
        config.polling_interval = interval
    if repo is not None:
        config.repo = repo
    if dry_run:
        config.dry_run = dry_run

    pid, is_valid = _validate_pid_file(config.pid_file)
    if is_valid:
        typer.echo(f"Orchestra server already running (PID: {pid})")
        raise typer.Exit(1)
    elif pid is not None:
        typer.echo(f"Cleaning up stale PID file (dead process {pid})")
        config.pid_file.unlink()

    log = logger.bind(domain="orchestra", action="serve")
    log.info(
        "Starting Orchestra server",
        interval=config.polling_interval,
        repo=config.repo,
        dry_run=config.dry_run,
    )

    typer.echo(
        f"Starting Orchestra server (interval: {config.polling_interval}s, "
        f"max_concurrent: {config.max_concurrent_flows})"
    )
    typer.echo("Press Ctrl+C to stop")

    poller = Poller(config)
    poller.start()


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
