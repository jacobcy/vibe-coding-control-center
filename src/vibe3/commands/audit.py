"""Audit evidence collection command.

Read-only command to collect evidence from flow store, GitHub, and git.
"""

from datetime import datetime
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from vibe3.clients import GitClient, GitHubClient, SQLiteClient
from vibe3.services.audit import (
    AuditEvidenceCollector,
    format_bundle_json,
    format_bundle_summary,
)

app = typer.Typer(
    name="audit",
    help="Audit evidence collection (read-only)",
    no_args_is_help=True,
)

console = Console()

# Type alias for format option
FormatOption = Annotated[
    str,
    typer.Option(
        "--format",
        "-f",
        help="Output format: json or table",
        case_sensitive=False,
    ),
]

_ISSUE_OPT = Annotated[
    int | None,
    typer.Option("--issue", help="Issue number to collect evidence for"),
]

_BRANCH_OPT = Annotated[
    str | None,
    typer.Option("--branch", help="Flow branch name to collect evidence for"),
]

_TIME_WINDOW_START_OPT = Annotated[
    str | None,
    typer.Option("--time-window-start", help="ISO8601 start timestamp for time window"),
]

_TIME_WINDOW_END_OPT = Annotated[
    str | None,
    typer.Option("--time-window-end", help="ISO8601 end timestamp for time window"),
]

_OUTPUT_OPT = Annotated[
    Path | None,
    typer.Option("--output", "-o", help="Output file path (default: stdout)"),
]


@app.command(name="bundle")
def bundle(
    issue: _ISSUE_OPT = None,
    branch: _BRANCH_OPT = None,
    time_window_start: _TIME_WINDOW_START_OPT = None,
    time_window_end: _TIME_WINDOW_END_OPT = None,
    output: _OUTPUT_OPT = None,
    format: FormatOption = "json",  # type: ignore
) -> None:
    """Collect audit evidence bundle from flow store, GitHub, and git.

    This command is read-only and does not modify any external state.

    At least one of --issue or --branch must be specified.

    Output includes metadata header with:
    - Data sources (flow store, GitHub, git)
    - Time window (if specified)
    - Repository info (owner, name, commit)
    """
    # Validate at least one subject is specified
    if not issue and not branch:
        console.print(
            "[red]Error:[/red] At least one of --issue or --branch must be specified"
        )
        raise typer.Exit(1)

    # Parse time window if provided
    time_window = None
    if time_window_start or time_window_end:
        try:
            start = (
                datetime.fromisoformat(time_window_start) if time_window_start else None
            )
            end = datetime.fromisoformat(time_window_end) if time_window_end else None
            if start and end:
                time_window = (start, end)
            else:
                console.print(
                    "[yellow]Warning:[/yellow] Incomplete time window, ignoring"
                )
        except ValueError as e:
            console.print(f"[red]Error:[/red] Invalid time window format: {e}")
            raise typer.Exit(1)

    # Determine mode
    mode = "manual"
    if issue and not branch:
        mode = "issue"
    elif branch and not issue:
        mode = "flow"
    elif time_window:
        mode = "time_window"

    # Initialize clients
    try:
        sqlite_client = SQLiteClient()
        github_client = GitHubClient()
        git_client = GitClient()
    except Exception as e:
        console.print(f"[red]Error:[/red] Failed to initialize clients: {e}")
        raise typer.Exit(1)

    # Initialize collector
    collector = AuditEvidenceCollector(
        sqlite_client=sqlite_client,
        github_client=github_client,
        git_client=git_client,
    )

    # Collect evidence
    console.print("[dim]Collecting evidence...[/dim]")
    try:
        bundle = collector.assemble_bundle(
            mode=mode,
            issue_number=issue,
            branch=branch,
            time_window=time_window,
        )
    except Exception as e:
        console.print(f"[red]Error:[/red] Failed to collect evidence: {e}")
        raise typer.Exit(1)

    # Format output
    if format.lower() == "json":
        output_text = format_bundle_json(bundle)
    else:
        output_text = format_bundle_summary(bundle)

    # Output to file or stdout
    if output:
        output.write_text(output_text)
        console.print(f"[green]✓[/green] Evidence bundle written to: {output}")
    else:
        console.print(output_text)

    # Print metadata header
    console.print("\n[dim]--- Metadata ---[/dim]")
    console.print(f"[dim]Bundle ID: {bundle.id}[/dim]")
    console.print(f"[dim]Schema Version: {bundle.schema_version}[/dim]")
    console.print(f"[dim]Mode: {bundle.collection_context.mode}[/dim]")
    console.print(
        f"[dim]Source Machine: {bundle.collection_context.source_machine}[/dim]"
    )
    console.print(
        f"[dim]Source Commit: {bundle.collection_context.source_commit}[/dim]"
    )
    console.print(f"[dim]Created: {bundle.created_at}[/dim]")
