"""PR UI components."""

from rich.table import Table

from vibe3.models.pr import PRResponse, ReviewResponse, VersionBumpResponse
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


def render_pr_merged(pr: PRResponse) -> None:
    console.print(f"[green]✓[/] PR #{pr.number} merged successfully!")
    console.print(f"[dim]Branch {pr.head_branch} has been deleted[/]")


def render_version_bump(response: VersionBumpResponse) -> None:
    console.print("\n[bold]Version Bump Calculation[/]")
    console.print(f"\ncurrent  {response.current_version}")
    console.print(f"bump     [yellow]{response.bump_type.value}[/]")
    console.print(f"next     [green]{response.next_version}[/]")
    console.print(f"\n[dim]{response.reason}[/]")


def render_pr_list(prs: list[PRResponse]) -> None:
    """Render list of PRs as a borderless table."""
    table = Table(box=None, pad_edge=False, show_header=True, header_style="bold dim")
    table.add_column("number", style="cyan", no_wrap=True)
    table.add_column("title", style="white")
    table.add_column("status", style="yellow")
    table.add_column("branch", style="dim")

    for pr in prs:
        status = pr.state.value + (" (draft)" if pr.draft else "")
        table.add_row(f"#{pr.number}", pr.title[:50], status, pr.head_branch)

    console.print(table)


def render_error(message: str) -> None:
    console.print(f"[red]✗[/] {message}")


def render_warning(message: str) -> None:
    console.print(f"[yellow]⚠[/] {message}")


def render_pr_review(response: ReviewResponse) -> None:
    console.print(f"[green]✓[/] Review completed for PR #{response.pr_number}")
    if response.published:
        console.print("[dim]Review published as a comment[/]")
    else:
        console.print("[dim]Review not published[/]")
    console.print("\n[bold]Review Content:[/]\n")
    console.print(response.review_body)
