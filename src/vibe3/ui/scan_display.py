"""UI display functions for scan command.

Result display helpers have moved to vibe3.ui.result_display — re-exported
here for backward compatibility.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Union

from rich.console import Console
from rich.table import Table

from vibe3.prompts import PromptMaterialSpec

# Re-export for backward compatibility — canonical location is result_display
from vibe3.ui.result_display import (  # noqa: F401
    display_codeagent_result,
    display_execution_result,
)

if TYPE_CHECKING:
    pass


def display_supervisor_dry_run(
    console: Console,
    total_scanned: int,
    candidates: list[dict],
) -> None:
    """Display supervisor scan dry-run candidate information.

    Note: Prompt Composition is now handled by CodeagentBackend.run(dry_run=True)
    This function only displays candidate list and scan summary.

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
