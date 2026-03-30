"""PR UI components."""

from vibe3.models.pr import PRResponse
from vibe3.ui.console import console


def render_pr_created(pr: PRResponse) -> None:
    console.print("[green]✓[/] Draft PR created successfully!")
    console.print(f"\n[cyan]PR #{pr.number}[/]: {pr.title}")
    console.print(f"[dim]{pr.url}[/]")
    console.print(
        f"\nBranch: [yellow]{pr.head_branch}[/] → [yellow]{pr.base_branch}[/]"
    )


def render_pr_confirmed(pr: PRResponse) -> None:
    """Render existing PR confirmation with current state."""
    status = pr.state.value
    if status == "MERGED":
        prefix = "[yellow]ℹ[/] PR already exists and is merged"
    elif status == "CLOSED":
        prefix = "[yellow]ℹ[/] PR already exists and is closed"
    elif pr.draft:
        prefix = "[yellow]ℹ[/] Draft PR already exists"
    else:
        prefix = "[yellow]ℹ[/] PR already exists"

    console.print(prefix)
    console.print(f"\n[cyan]PR #{pr.number}[/]: {pr.title}")
    console.print(f"[dim]{pr.url}[/]")
    console.print(
        f"\nBranch: [yellow]{pr.head_branch}[/] → [yellow]{pr.base_branch}[/]"
    )


def render_pr_details(pr: PRResponse) -> None:
    console.print(f"\n[bold cyan]PR #{pr.number}[/]: {pr.title}\n")

    status_color = {
        "OPEN": "yellow",
        "CLOSED": "red",
        "MERGED": "green",
        "DRAFT": "dim",
    }.get(pr.state.value, "white")
    console.print(f"Status: [{status_color}]{pr.state.value}[/{status_color}]")
    if pr.draft:
        console.print("[dim](Draft)[/dim]")

    console.print(
        f"\nBranch: [yellow]{pr.head_branch}[/] → [yellow]{pr.base_branch}[/]"
    )
    console.print(f"\nURL: [link={pr.url}]{pr.url}[/link]")

    if pr.metadata:
        console.print("\n[bold]Vibe3 Metadata:[/]")
        if pr.metadata.task_issue:
            console.print(f"  task_issue  #{pr.metadata.task_issue}")
        if pr.metadata.flow_slug:
            console.print(f"  flow        {pr.metadata.flow_slug}")
        if pr.metadata.spec_ref:
            console.print(f"  spec_ref    {pr.metadata.spec_ref}")
        if pr.metadata.planner:
            console.print(f"  planner     {pr.metadata.planner}")
        if pr.metadata.executor:
            console.print(f"  executor    {pr.metadata.executor}")

    if pr.body:
        console.print("\n[bold]Description:[/]")
        body_preview = pr.body[:200] + ("..." if len(pr.body) > 200 else "")
        console.print(body_preview)


def render_pr_ready(pr: PRResponse) -> None:
    console.print(f"[green]✓[/] PR #{pr.number} marked as ready for review")
    console.print(f"[dim]{pr.url}[/]")


def render_error(message: str) -> None:
    console.print(f"[red]✗[/] {message}")
