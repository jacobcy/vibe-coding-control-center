"""vibe3 serve command."""

from typing import Annotated

import typer
from loguru import logger

from vibe3.observability.logger import setup_logging
from vibe3.orchestra.config import OrchestraConfig
from vibe3.orchestra.poller import Poller

app = typer.Typer(
    help="Orchestra daemon for GitHub label-driven orchestration",
    no_args_is_help=True,
)


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
    """Start Orchestra daemon to monitor GitHub labels.

    The daemon monitors GitHub issues for state label changes and
    triggers corresponding commands (plan/run/review).

    Examples:
        vibe3 serve start
        vibe3 serve start --interval 30
        vibe3 serve start --repo owner/repo --dry-run
    """
    setup_logging(verbose=verbose)

    config = OrchestraConfig(
        polling_interval=interval,
        repo=repo,
        dry_run=dry_run,
    )

    log = logger.bind(domain="orchestra", action="serve")
    log.info(
        "Starting Orchestra daemon",
        interval=config.polling_interval,
        repo=config.repo,
        dry_run=config.dry_run,
    )

    poller = Poller(config)
    poller.start()


@app.command()
def status() -> None:
    """Show Orchestra daemon status."""
    config = OrchestraConfig.from_settings()
    pid_file = config.pid_file

    if not pid_file.exists():
        typer.echo("Orchestra daemon is not running")
        raise typer.Exit(0)

    pid = pid_file.read_text().strip()
    typer.echo(f"Orchestra daemon running (PID: {pid})")


@app.command()
def stop() -> None:
    """Stop Orchestra daemon."""
    config = OrchestraConfig.from_settings()
    pid_file = config.pid_file

    if not pid_file.exists():
        typer.echo("Orchestra daemon is not running")
        raise typer.Exit(0)

    import os
    import signal

    pid = int(pid_file.read_text().strip())
    try:
        os.kill(pid, signal.SIGTERM)
        typer.echo(f"Stopped Orchestra daemon (PID: {pid})")
    except ProcessLookupError:
        typer.echo(f"Process {pid} not found, cleaning up")
        pid_file.unlink()
