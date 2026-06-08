"""PR UI components."""

from typing import TYPE_CHECKING

from vibe3.models import PRResponse
from vibe3.ui.console_impl import console
from vibe3.utils import format_age_aware_time

if TYPE_CHECKING:
    from vibe3.analysis import LocalReviewReport


def render_pr_created(pr: PRResponse) -> None:
    console.print("[green]✓[/] PR created successfully!")
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

    # CI status display
    if pr.ci_checks:
        passed = all(c.bucket == "pass" for c in pr.ci_checks)
        failed = [c for c in pr.ci_checks if c.bucket == "fail"]
        pending = [c for c in pr.ci_checks if c.bucket == "pending"]
        other = [c for c in pr.ci_checks if c.bucket not in ("pass", "fail", "pending")]

        if passed:
            console.print("\n[bold]CI Status:[/] [green]✓ All checks passed[/]")
        elif failed:
            console.print(
                "\n[bold]CI Status:[/] [red]✗ {} check(s) failed[/]".format(len(failed))
            )
            for check in failed:
                console.print(
                    f"  [red]✗[/] [bold]{check.name}[/] [dim]({check.state})[/]"
                )
                if check.failure_category:
                    console.print(
                        f"    [dim]Failure category:[/] {check.failure_category}"
                    )
                if check.failure_command:
                    console.print(f"    [dim]Inspect with:[/] {check.failure_command}")
                if check.workflow:
                    console.print(f"    [dim]Workflow:[/] {check.workflow}")
                if check.description:
                    console.print(f"    [dim]Description:[/] {check.description}")
                console.print(f"    [dim][link={check.link}]View details[/link][/]")
        elif pending:
            console.print(
                "\n[bold]CI Status:[/] [yellow]● {} check(s) pending[/]".format(
                    len(pending)
                )
            )
            for check in pending:
                console.print(f"  [yellow]●[/] {check.name}")
        elif other:
            # Handle unknown buckets (skipping, cancel, etc.)
            console.print(
                "\n[bold]CI Status:[/] [dim]{} check(s) in other state[/]".format(
                    len(other)
                )
            )
            for check in other:
                console.print(f"  [dim]○[/] {check.name} [dim]({check.bucket})[/]")
    else:
        # Fallback to ci_passed / ci_status for backward compat
        if pr.ci_passed:
            console.print("\n[bold]CI Status:[/] [green]✓ Passed[/]")
        elif pr.ci_status:
            console.print(f"\n[bold]CI Status:[/] [dim]{pr.ci_status}[/]")

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
        console.print(pr.body)

    if pr.review_comments:
        console.print("\n[bold cyan]### Review Comments[/]")
        # Sort chronologically, None/missing timestamps sort to end
        sorted_reviews = sorted(
            pr.review_comments,
            key=lambda x: x.get("created_at") or "9999-99-99T99:99:99Z",
        )
        for comment in sorted_reviews:
            user = comment.get("user", {}).get("login", "unknown")
            body = comment.get("body", "")
            path = comment.get("path", "")
            line = comment.get("line", "")
            created = str(comment.get("created_at", ""))[:16].replace("T", " ")
            console.print(
                f"  [yellow]{user}[/] [dim]({created})[/] [cyan]{path}:{line}[/]"
            )
            console.print(f"    {body}")

    if pr.reviews:
        console.print("\n[bold cyan]### Reviews[/]")
        # Sort chronologically, None/missing timestamps sort to end
        sorted_reviews_list = sorted(
            pr.reviews,
            key=lambda x: x.get("submitted_at") or "9999-99-99T99:99:99Z",
        )
        for review in sorted_reviews_list:
            user = review.get("user", {}).get("login", "unknown")
            body = review.get("body", "")
            state = review.get("state", "COMMENTED")
            submitted = str(review.get("submitted_at", ""))[:16].replace("T", " ")
            state_color = {
                "APPROVED": "green",
                "CHANGES_REQUESTED": "red",
                "COMMENTED": "yellow",
            }.get(state, "dim")
            console.print(
                f"  [yellow]{user}[/] [dim]({submitted})[/] "
                f"[{state_color}]{state}[/{state_color}]"
            )
            if body:
                console.print(f"    {body}")

    if pr.comments:
        console.print("\n[bold cyan]### General Comments[/]")
        # Sort chronologically, None/missing timestamps sort to end
        sorted_comments = sorted(
            pr.comments,
            key=lambda x: x.get("createdAt") or "9999-99-99T99:99:99Z",
        )
        for comment in sorted_comments:
            # GitHub API returns "user.login" not "author.login"
            user = comment.get("user", {}).get("login", "unknown")
            body = comment.get("body", "")
            created = str(comment.get("createdAt", ""))[:16].replace("T", " ")
            console.print(f"  [yellow]{user}[/] [dim]({created})[/]")
            console.print(f"    {body}")


def render_pr_ready(
    pr: PRResponse, requested_reviewers: list[str] | None = None
) -> None:
    """Render PR ready result with optional AI review request."""
    console.print(f"[green]✓[/] PR #{pr.number} marked as ready for review")
    console.print("[blue]📝[/] Reviewer briefing updated")
    if requested_reviewers:
        reviewers_str = ", ".join(requested_reviewers)
        console.print(f"[yellow]🤖[/] AI review requested: {reviewers_str}")
    console.print(f"[dim]{pr.url}[/]")


def render_local_review_summary(
    local_review: "LocalReviewReport | None",
) -> None:
    """Render local pre-push review summary.

    Args:
        local_review: LocalReviewReport if found, None otherwise
    """
    console.print("\n[bold]### Local Review[/]")

    if not local_review:
        console.print("- [dim]无本地 review evidence[/]")
        return

    console.print("- [cyan]Status[/]: Found")
    if local_review.risk_level:
        console.print(f"- [cyan]Risk Level[/]: {local_review.risk_level}")
    else:
        console.print("- [cyan]Risk Level[/]: [dim]N/A[/]")

    if local_review.risk_score:
        console.print(f"- [cyan]Risk Score[/]: {local_review.risk_score}")
    else:
        console.print("- [cyan]Risk Score[/]: [dim]N/A[/]")

    if local_review.verdict:
        console.print(f"- [cyan]Verdict[/]: {local_review.verdict}")
    else:
        console.print("- [cyan]Verdict[/]: [dim]N/A[/]")

    console.print(f"- [cyan]Report[/]: {local_review.report_path}")

    if local_review.created_at:
        created_str = format_age_aware_time(local_review.created_at)
        console.print(f"- [cyan]Created At[/]: {created_str}")
