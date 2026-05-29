"""Task management commands - update."""

from typing import Annotated

import typer

from vibe3.clients.github_labels import GhIssueLabelPort
from vibe3.commands.command_options import TraceMinMsOption, TraceOption
from vibe3.commands.common import enable_method_trace, validate_trace_options
from vibe3.exceptions import SystemError


def update(
    issue_number: Annotated[int, typer.Argument(help="Issue number")],
    add_label: Annotated[
        list[str] | None, typer.Option("--add-label", help="Add label to issue")
    ] = None,
    remove_label: Annotated[
        list[str] | None, typer.Option("--remove-label", help="Remove label from issue")
    ] = None,
    trace: TraceOption = False,
    min_ms: TraceMinMsOption = None,
) -> None:
    """Update issue labels.

    Thin wrapper over GitHub issue label operations.
    For complex state transitions, use vibe3 flow lifecycle commands instead.

    Examples:
      vibe3 task update 123 --add-label "state/handoff"
      vibe3 task update 456 --add-label "priority/high" --remove-label "priority/low"
    """
    validate_trace_options(trace, min_ms)
    if trace:
        enable_method_trace(min_ms=min_ms)

    if not add_label and not remove_label:
        typer.echo(
            "Error: Must specify at least one --add-label or --remove-label",
            err=True,
        )
        raise typer.Exit(1)

    port = GhIssueLabelPort()

    try:
        # Add labels
        if add_label:
            for label in add_label:
                ok = port.add_issue_label(issue_number, label)
                if not ok:
                    raise SystemError(
                        f"Failed to add label '{label}' to issue #{issue_number}"
                    )
                typer.echo(f"✓ Added label '{label}' to issue #{issue_number}")

        # Remove labels
        if remove_label:
            for label in remove_label:
                ok = port.remove_issue_label(issue_number, label)
                if not ok:
                    raise SystemError(
                        f"Failed to remove label '{label}' from issue #{issue_number}"
                    )
                typer.echo(f"✓ Removed label '{label}' from issue #{issue_number}")

    except SystemError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1) from e


def register_manage_commands(app: typer.Typer) -> None:
    """Register task management commands."""
    app.command(name="update")(update)
