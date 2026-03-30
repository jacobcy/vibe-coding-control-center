"""vibe3 orchestra command - Orchestra system management."""

from typing import Annotated

import typer

from vibe3.observability import setup_logging
from vibe3.orchestra.config import OrchestraConfig
from vibe3.orchestra.services.status_service import OrchestraStatusService

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

    if json_output:
        import json
        from dataclasses import asdict

        def serialize_state(obj: object) -> object:
            if hasattr(obj, "value"):
                return obj.value
            return obj

        data = asdict(snapshot)
        # Convert IssueState enum to string
        for entry in data.get("active_issues", []):
            if entry.get("state"):
                entry["state"] = (
                    entry["state"].value
                    if hasattr(entry["state"], "value")
                    else entry["state"]
                )
        typer.echo(json.dumps(data, indent=2, default=serialize_state))
    else:
        typer.echo(service.format_snapshot(snapshot))
