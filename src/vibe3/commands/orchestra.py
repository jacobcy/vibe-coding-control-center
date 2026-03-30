"""vibe3 orchestra command - Orchestra system management."""

from typing import Annotated

import typer

from vibe3.observability import setup_logging
from vibe3.orchestra.config import OrchestraConfig
from vibe3.orchestra.services.status_service import OrchestraStatusService
from vibe3.ui.orchestra_ui import render_orchestra_status

app = typer.Typer(
    help="Orchestra system management commands",
    no_args_is_help=True,
)


@app.command()
def status(
    json_output: Annotated[
        bool,
        typer.Option("--json", "-j", help="Output as JSON"),
    ] = False,
    verbose: Annotated[
        int,
        typer.Option("-v", "--verbose", count=True, help="Increase verbosity"),
    ] = 0,
) -> None:
    """Show current Orchestra system status.

    Displays:
    - Active issues assigned to managers
    - Flow state for each issue
    - Worktree status
    - PR status

    Examples:
        vibe3 orchestra status
        vibe3 orchestra status --json
    """
    setup_logging(verbose=verbose)

    config = OrchestraConfig.from_settings()
    service = OrchestraStatusService(config)
    snapshot = service.snapshot()

    render_orchestra_status(snapshot, json_output)
