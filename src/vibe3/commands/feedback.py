"""Feedback CLI commands for managing observations."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Optional

import typer
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from vibe3.services.feedback.import_service import FeedbackImportService
from vibe3.services.feedback.read_service import FeedbackReadService
from vibe3.services.feedback.write_service import FeedbackWriteService

app = typer.Typer(
    name="feedback",
    help="Manage feedback observations for audit trail",
    no_args_is_help=True,
)

console = Console()


@app.command(name="write")
def write_command(
    files: Annotated[
        list[Path],
        typer.Argument(
            help="YAML file(s) containing observations to write",
        ),
    ] = [],
    stdin: Annotated[
        bool,
        typer.Option(
            "--stdin",
            help="Read YAML from stdin instead of files",
        ),
    ] = False,
) -> None:
    """Write observation(s) from YAML file(s) or stdin to database.

    Examples:
        vibe3 feedback write observation.yaml
        vibe3 feedback write obs1.yaml obs2.yaml
        cat observation.yaml | vibe3 feedback write --stdin
    """
    write_service = FeedbackWriteService()

    if stdin:
        import sys

        data = sys.stdin.read()
        if not data.strip():
            console.print("[red]Error: Empty input from stdin[/red]")
            raise typer.Exit(1)

        try:
            obs = write_service.write_from_stdin(data)
            console.print(f"[green]✓[/green] Wrote observation {obs.observation_id}")
        except ValueError as e:
            console.print(f"[red]Error:[/red] {e}")
            raise typer.Exit(1)
        return

    if not files:
        console.print(
            "[red]Error:[/red] No files specified. "
            "Use --stdin or provide file paths."
        )
        raise typer.Exit(1)

    for file_path in files:
        if not file_path.exists():
            console.print(f"[red]Error:[/red] File not found: {file_path}")
            continue

        try:
            obs = write_service.write_from_file(file_path)
            console.print(f"[green]✓[/green] {file_path}: {obs.observation_id}")
        except ValueError as e:
            console.print(f"[red]✗[/red] {file_path}: {e}")


@app.command(name="validate")
def validate_command(
    files: Annotated[
        list[Path],
        typer.Argument(
            help="YAML file(s) to validate against AuditObservation model",
        ),
    ],
) -> None:
    """Validate YAML file(s) against AuditObservation model.

    Examples:
        vibe3 feedback validate observation.yaml
        vibe3 feedback validate obs1.yaml obs2.yaml
    """
    write_service = FeedbackWriteService()

    for file_path in files:
        if not file_path.exists():
            console.print(f"[red]✗[/red] {file_path}: File not found")
            continue

        is_valid, error = write_service.validate_file(file_path)
        if is_valid:
            console.print(f"[green]✓[/green] {file_path}: Valid")
        else:
            console.print(f"[red]✗[/red] {file_path}: {error}")


@app.command(name="list")
def list_command(
    source: Annotated[
        Optional[str],
        typer.Option(
            "--source",
            "-s",
            help="Filter by source material",
        ),
    ] = None,
    symptom: Annotated[
        Optional[str],
        typer.Option(
            "--symptom",
            help="Filter by symptom (substring match)",
        ),
    ] = None,
    failure_mode: Annotated[
        Optional[str],
        typer.Option(
            "--failure-mode",
            "-f",
            help="Filter by observed failure mode",
        ),
    ] = None,
    limit: Annotated[
        int,
        typer.Option(
            "--limit",
            "-l",
            help="Maximum number of results",
        ),
    ] = 20,
) -> None:
    """List observations with optional filters.

    Examples:
        vibe3 feedback list
        vibe3 feedback list --source governance/audit-observation
        vibe3 feedback list --failure-mode scope_mismatch
        vibe3 feedback list --symptom "missing output"
    """
    read_service = FeedbackReadService()
    observations = read_service.list_observations(
        source=source,
        symptom=symptom,
        failure_mode=failure_mode,
        limit=limit,
    )

    if not observations:
        console.print("[dim]No observations found[/dim]")
        return

    table = Table(
        title="Observations",
        box=box.SIMPLE,
        show_header=True,
        header_style="bold",
    )
    table.add_column("ID", style="cyan")
    table.add_column("Type", style="green")
    table.add_column("Failure Mode", style="yellow")
    table.add_column("Confidence", style="magenta")
    table.add_column("Created", style="dim")

    for obs in observations:
        # Truncate ID for display
        obs_id = obs["observation_id"]
        if len(obs_id) > 20:
            obs_id = obs_id[:17] + "..."

        # Format created_at
        created = obs["created_at"]
        if len(created) > 19:
            created = created[:19]

        table.add_row(
            obs_id,
            obs["observation_type"][:30],
            obs["observed_failure_mode"],
            obs["confidence"],
            created,
        )

    console.print(table)
    console.print(f"[dim]Showing {len(observations)} observation(s)[/dim]")


@app.command(name="show")
def show_command(
    observation_id: Annotated[
        str,
        typer.Argument(
            help="Unique observation identifier",
        ),
    ],
) -> None:
    """Show full details of an observation.

    Examples:
        vibe3 feedback show obs-20260620T120000Z-abc12345
    """
    read_service = FeedbackReadService()
    obs = read_service.show_observation(observation_id)

    if obs is None:
        console.print(f"[red]Error:[/red] Observation not found: {observation_id}")
        raise typer.Exit(1)

    # Build detailed panel
    content = []
    content.append(f"[bold]Type:[/bold] {obs['observation_type']}")
    content.append(f"[bold]Source:[/bold] {obs['source_material']}")
    content.append(f"[bold]Status:[/bold] {obs['flow_status']}")
    content.append("")
    content.append("[bold]Symptom:[/bold]")
    content.append(f"  {obs['symptom']}")
    content.append("")
    content.append(f"[bold]Failure Mode:[/bold] {obs['observed_failure_mode']}")
    content.append(f"[bold]Confidence:[/bold] {obs['confidence']}")
    content.append("")

    # Subject info
    if obs.get("subject_issue_number") or obs.get("subject_branch"):
        content.append("[bold]Subject:[/bold]")
        if obs.get("subject_issue_number"):
            content.append(f"  Issue: #{obs['subject_issue_number']}")
        if obs.get("subject_branch"):
            content.append(f"  Branch: {obs['subject_branch']}")
        if obs.get("subject_pr_number"):
            content.append(f"  PR: #{obs['subject_pr_number']}")
        content.append("")

    # Interpretation
    if obs.get("interpretation_reasoning"):
        content.append("[bold]Interpretation:[/bold]")
        content.append(f"  {obs['interpretation_reasoning']}")
        if obs.get("interpretation_likely_agent_failure"):
            failure = obs["interpretation_likely_agent_failure"]
            content.append(f"  Likely failure: {failure}")
        content.append("")

    # Clustering
    content.append("[bold]Clustering:[/bold]")
    content.append(f"  Suitable: {bool(obs.get('suitable_for_clustering', True))}")
    if obs.get("suggested_cluster_key"):
        content.append(f"  Key: {obs['suggested_cluster_key']}")
    content.append(f"  Requires review: {bool(obs.get('requires_human_review', True))}")

    panel = Panel(
        "\n".join(content),
        title=f"[cyan]{observation_id}[/cyan]",
        box=box.ROUNDED,
    )
    console.print(panel)


@app.command(name="stats")
def stats_command(
    group_by: Annotated[
        str,
        typer.Option(
            "--group-by",
            "-g",
            help="Group by field (failure_mode or cluster_key)",
        ),
    ] = "failure_mode",
) -> None:
    """Show aggregated observation statistics.

    Examples:
        vibe3 feedback stats
        vibe3 feedback stats --group-by cluster_key
    """
    read_service = FeedbackReadService()

    try:
        stats = read_service.get_stats(group_by=group_by)
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    if not stats:
        console.print("[dim]No observations found[/dim]")
        return

    table = Table(
        title=f"Observations by {group_by}",
        box=box.SIMPLE,
        show_header=True,
        header_style="bold",
    )
    table.add_column(group_by.replace("_", " ").title(), style="cyan")
    table.add_column("Count", style="green", justify="right")

    for key, count in sorted(stats.items(), key=lambda x: x[1], reverse=True):
        table.add_row(str(key), str(count))

    console.print(table)
    console.print(f"[dim]Total: {sum(stats.values())} observation(s)[/dim]")


@app.command(name="import")
def import_command(
    from_dir: Annotated[
        Path,
        typer.Option(
            "--from",
            help="Source directory containing YAML files",
        ),
    ] = Path(".git/shared/observations/"),
) -> None:
    """Import observations from directory.

    Scans for .yaml/.yml files in the specified directory and imports them
    to the database. Handles errors gracefully, reporting counts.

    Examples:
        vibe3 feedback import
        vibe3 feedback import --from .git/shared/observations/
    """
    import_service = FeedbackImportService()

    try:
        imported, skipped = import_service.import_from_directory(from_dir)
    except FileNotFoundError:
        console.print(f"[red]Error:[/red] Directory not found: {from_dir}")
        raise typer.Exit(1)
    except NotADirectoryError:
        console.print(f"[red]Error:[/red] Not a directory: {from_dir}")
        raise typer.Exit(1)

    console.print(f"[green]✓[/green] Imported: {imported}")
    if skipped > 0:
        console.print(f"[yellow]⚠[/yellow] Skipped: {skipped}")
