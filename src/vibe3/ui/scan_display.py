"""UI display functions for scan command."""

from __future__ import annotations

from typing import TYPE_CHECKING, Union

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from vibe3.prompts import PromptMaterialSpec

if TYPE_CHECKING:
    from vibe3.agents import CodeagentResult
    from vibe3.models import ExecutionLaunchResult


def display_governance_dry_run(
    console: Console, material_name: str, prompt_content: str
) -> None:
    """Display governance scan dry-run output.

    Args:
        console: Rich Console instance
        material_name: Governance material name/path
        prompt_content: Rendered prompt content
    """
    # Extract short name
    short_name = material_name
    if "/" in material_name:
        short_name = material_name.split("/")[-1]
    if short_name.endswith(".md"):
        short_name = short_name[:-3]

    # Header
    console.print("\n[bold]Governance Scan Dry-Run[/bold]")
    console.print(f"[cyan]Material:[/cyan] {short_name}")

    # Prompt preview
    console.print("\n[bold]Prompt Preview:[/bold]")
    console.print(Panel(prompt_content, title="Governance Prompt", border_style="blue"))

    # Summary
    console.print(f"\n[dim]Prompt length: {len(prompt_content)} characters[/dim]")
    console.print(f"[dim]Material: {material_name}[/dim]")
    console.print("[dim]Mode: dry-run (no execution)[/dim]\n")


def display_supervisor_dry_run(
    console: Console, total_scanned: int, candidates: list[dict]
) -> None:
    """Display supervisor scan dry-run output.

    Args:
        console: Rich Console instance
        total_scanned: Total number of open issues scanned
        candidates: List of candidate issues (number, title, labels)
    """
    console.print("\n[bold]Supervisor Scan Dry-Run[/bold]")
    console.print("[cyan]Mode:[/cyan] dry-run (no execution)\n")

    # Scan process simulation
    console.print("[bold]Scan Process:[/bold]")
    console.print(f"1. Queried {total_scanned} open issues")
    console.print("2. Filtered by 'supervisor' + 'state/handoff' labels")
    console.print("3. For each matching issue:")
    console.print("   - Build supervisor handoff prompt")
    console.print("   - Would dispatch supervisor-apply agent\n")

    # Display candidates
    if candidates:
        console.print(
            f"[bold]Found {len(candidates)} supervisor candidate(s):[/bold]\n"
        )

        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("Issue", style="yellow")
        table.add_column("Title", style="white")
        table.add_column("Labels", style="green")

        for issue in candidates[:10]:  # Show first 10
            labels_str = ", ".join(sorted(issue.get("labels", []))[:5])
            title = issue.get("title", "")[:60]  # Truncate
            table.add_row(f"#{issue['number']}", title, labels_str)

        console.print(table)

        if len(candidates) > 10:
            console.print(f"\n[dim]... and {len(candidates) - 10} more[/dim]")

        console.print(
            "\n[dim]In real mode, would dispatch supervisor-apply agent "
            "for each issue[/dim]"
        )
    else:
        console.print(
            f"[yellow]Scanned {total_scanned} open issues, "
            f"found 0 issues with supervisor + state/handoff labels[/yellow]\n"
        )

    console.print("\n[bold]Summary:[/bold]")
    console.print(f"[dim]• Total issues scanned: {total_scanned}[/dim]")
    console.print(f"[dim]• Matching candidates: {len(candidates)}[/dim]")
    console.print(
        "[dim]• Action: Would build and dispatch supervisor-apply prompts[/dim]"
    )
    console.print("[dim]• Mode: dry-run (no execution)[/dim]\n")


def display_material_list(
    console: Console,
    materials: Union[list[PromptMaterialSpec], list[dict]],
) -> None:
    """Display list of available governance materials.

    Args:
        console: Rich Console instance
        materials: List of material specs or dicts with name/description
    """
    if not materials:
        console.print("[yellow]No governance materials found[/yellow]")
        return

    console.print("\n[bold]Available Governance Materials[/bold]\n")

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Material", style="cyan", no_wrap=True)
    table.add_column("Description", style="white")

    for material in materials:
        # Handle both PromptMaterialSpec and dict
        if isinstance(material, PromptMaterialSpec):
            name = material.name
            description = material.name  # Fallback to filename
        else:
            name = material.get("name", "")
            description = material.get("description", name)

        # Extract short name
        short_name = name
        if "/" in name:
            short_name = name.split("/")[-1]
        if short_name.endswith(".md"):
            short_name = short_name[:-3]

        table.add_row(short_name, description)

    console.print(table)


def display_execution_result(console: Console, result: "ExecutionLaunchResult") -> None:
    """Display execution launch result from governance/supervisor dispatch.

    Args:
        console: Rich Console instance
        result: ExecutionLaunchResult from handler dispatch
    """
    console.print("\n[bold]Execution Launch Result[/bold]")

    if result.launched:
        console.print("[green]✓ Launched successfully[/green]")
        if result.backend:
            console.print(f"[cyan]Backend:[/cyan] {result.backend}")
        if result.model:
            console.print(f"[cyan]Model:[/cyan] {result.model}")
        if result.tmux_session:
            console.print(f"[cyan]Tmux session:[/cyan] {result.tmux_session}")
        if result.log_path:
            console.print(f"[cyan]Log path:[/cyan] {result.log_path}")
    else:
        if result.skipped:
            console.print("[yellow]⚠ Skipped[/yellow]")
        else:
            console.print("[red]✗ Launch failed[/red]")

        if result.reason:
            console.print(f"[cyan]Reason:[/cyan] {result.reason}")
        if result.reason_code:
            console.print(f"[cyan]Code:[/cyan] {result.reason_code}")

    console.print()  # Blank line for readability


def display_codeagent_result(
    console: Console,
    result: "CodeagentResult | None",
    label: str = "Execution",
) -> None:
    """Display CodeagentResult from plan/run execution.

    Args:
        console: Rich Console instance
        result: CodeagentResult from handler execution
        label: Label for the result header (e.g., "Plan", "Run")
    """
    if result is None:
        console.print(f"\n[bold]{label} Result[/bold]")
        console.print("[yellow]No result returned (async mode)[/yellow]\n")
        return

    console.print(f"\n[bold]{label} Result[/bold]")
    if result.success:
        console.print("[green]✓ Completed successfully[/green]")
    else:
        console.print("[red]✗ Failed[/red]")
        if result.stderr:
            console.print(f"[red]{result.stderr}[/red]")

    if result.log_path:
        console.print(f"[cyan]Log path:[/cyan] {result.log_path}")
    if result.handoff_file:
        console.print(f"[cyan]Handoff:[/cyan] {result.handoff_file}")
    if result.tmux_session:
        console.print(f"[cyan]Tmux session:[/cyan] {result.tmux_session}")

    console.print()  # Blank line for readability
