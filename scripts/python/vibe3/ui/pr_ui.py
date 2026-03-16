"""PR UI components."""
from rich import print
from rich.table import Table

from vibe3.models.pr import PRResponse, ReviewResponse, VersionBumpResponse


def render_pr_created(pr: PRResponse) -> None:
    """Render PR created message.

    Args:
        pr: PR response
    """
    print(f"[green]✓[/] Draft PR created successfully!")
    print(f"\n[cyan]PR #{pr.number}[/]: {pr.title}")
    print(f"[dim]{pr.url}[/]")
    print(f"\nBranch: [yellow]{pr.head_branch}[/] → [yellow]{pr.base_branch}[/]")


def render_pr_details(pr: PRResponse) -> None:
    """Render PR details.

    Args:
        pr: PR response
    """
    print(f"\n[bold cyan]PR #{pr.number}[/]: {pr.title}\n")

    # Status
    status_color = {
        "OPEN": "yellow",
        "CLOSED": "red",
        "MERGED": "green",
        "DRAFT": "dim",
    }.get(pr.state.value, "white")

    print(f"Status: [{status_color}]{pr.state.value}[/{status_color}]")
    if pr.draft:
        print("[dim](Draft)[/dim]")

    # Branches
    print(f"\nBranch: [yellow]{pr.head_branch}[/] → [yellow]{pr.base_branch}[/]")

    # URL
    print(f"\nURL: [link={pr.url}]{pr.url}[/link]")

    # Metadata
    if pr.metadata:
        print("\n[bold]Vibe3 Metadata:[/]")
        if pr.metadata.task_issue:
            print(f"  Task Issue: #{pr.metadata.task_issue}")
        if pr.metadata.flow_slug:
            print(f"  Flow: {pr.metadata.flow_slug}")
        if pr.metadata.spec_ref:
            print(f"  Spec Ref: {pr.metadata.spec_ref}")
        if pr.metadata.planner:
            print(f"  Planner: {pr.metadata.planner}")
        if pr.metadata.executor:
            print(f"  Executor: {pr.metadata.executor}")

    # Body
    if pr.body:
        print(f"\n[bold]Description:[/]")
        # Show first 200 characters of body
        body_preview = pr.body[:200]
        if len(pr.body) > 200:
            body_preview += "..."
        print(body_preview)


def render_pr_ready(pr: PRResponse) -> None:
    """Render PR ready message.

    Args:
        pr: PR response
    """
    print(f"[green]✓[/] PR #{pr.number} marked as ready for review")
    print(f"[dim]{pr.url}[/]")


def render_pr_merged(pr: PRResponse) -> None:
    """Render PR merged message.

    Args:
        pr: PR response
    """
    print(f"[green]✓[/] PR #{pr.number} merged successfully!")
    print(f"[dim]Branch {pr.head_branch} has been deleted[/]")


def render_version_bump(response: VersionBumpResponse) -> None:
    """Render version bump calculation.

    Args:
        response: Version bump response
    """
    print(f"\n[bold]Version Bump Calculation[/]")
    print(f"\nCurrent version: [cyan]{response.current_version}[/]")
    print(f"Bump type: [yellow]{response.bump_type.value}[/]")
    print(f"Next version: [green]{response.next_version}[/]")
    print(f"\nReason: [dim]{response.reason}[/]")


def render_pr_list(prs: list[PRResponse]) -> None:
    """Render list of PRs.

    Args:
        prs: List of PR responses
    """
    table = Table(title="Pull Requests")
    table.add_column("Number", style="cyan", no_wrap=True)
    table.add_column("Title", style="white")
    table.add_column("Status", style="yellow")
    table.add_column("Branch", style="dim")

    for pr in prs:
        status = pr.state.value
        if pr.draft:
            status += " (draft)"

        table.add_row(
            f"#{pr.number}",
            pr.title[:50],
            status,
            pr.head_branch,
        )

    print(table)


def render_error(message: str) -> None:
    """Render error message.

    Args:
        message: Error message
    """
    print(f"[red]Error:[/] {message}")


def render_warning(message: str) -> None:
    """Render warning message.

    Args:
        message: Warning message
    """
    print(f"[yellow]Warning:[/] {message}")


def render_pr_review(response: ReviewResponse) -> None:
    """Render PR review.

    Args:
        response: Review response
    """
    print(f"[green]✓[/] Review completed for PR #{response.pr_number}")

    if response.published:
        print("[dim]Review has been published as a comment[/]")
    else:
        print("[dim]Review was not published[/]")

    print(f"\n[bold]Review Content:[/]\n")
    print(response.review_body)