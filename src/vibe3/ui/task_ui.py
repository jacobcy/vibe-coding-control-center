"""Task UI rendering."""

import json
import re
from typing import TYPE_CHECKING

from vibe3.ui.console import console
from vibe3.ui.flow_ui_primitives import resolve_ref_path
from vibe3.utils.constants import AUTOMATED_MARKERS
from vibe3.utils.path_helpers import ref_to_handoff_cmd

if TYPE_CHECKING:
    from vibe3.services.task_service import TaskShowResult


def build_task_show_payload(task_result: "TaskShowResult") -> dict[str, object]:
    """Build a single JSON payload for task show."""
    return task_result.to_payload()


def render_task_show(
    task_result: "TaskShowResult",
    json_output: bool,
) -> None:
    """Render task show output.

    Args:
        task_result: Task show query result
        json_output: If True, output as JSON; otherwise formatted text
    """
    # Handle case where no flow exists
    if not task_result.local_task:
        # Check if branch is an issue number - try to show basic issue info
        branch = task_result.branch
        if branch.isdigit():
            # Branch is an issue number without flow
            # Try to fetch and display basic issue info
            if task_result.issue_title or task_result.issue_state:
                console.print(f"[yellow]No flow found for issue #{branch}[/]")
                console.print()
                console.print("[bold]Issue Info[/]")
                if task_result.issue_title:
                    console.print(f"Title:  {task_result.issue_title}")
                if task_result.issue_state:
                    console.print(f"State:  {task_result.issue_state.lower()}")
                if task_result.pr_summary:
                    pr = task_result.pr_summary
                    console.print("\n[bold]PR / CI[/]")
                    console.print(f"PR: #{pr.number} {pr.state} {pr.title}")
                    if pr.checks:
                        console.print(f"Checks: {pr.checks}")
                return
            # No issue info available
            console.print(f"[yellow]No flow found for issue #{branch}[/]")
            console.print("Tip: Use 'vibe3 flow new' to create a flow")
            return
        # Non-numeric branch without flow
        console.print(f"[yellow]No flow found: {branch}[/]")
        return

    task = task_result.local_task
    if json_output:
        console.print(
            json.dumps(
                build_task_show_payload(task_result),
                indent=2,
                default=str,
            ),
            markup=False,
            highlight=False,
            soft_wrap=True,
        )
        return

    console.print("[bold]Current Task[/]")
    console.print(f"Branch: {task.branch}")
    console.print(f"Flow:   {task.flow_slug} ({task.flow_status})")
    if task.task_issue_number:
        title_suffix = f"  {task_result.issue_title}" if task_result.issue_title else ""
        console.print(f"Task:   #{task.task_issue_number}{title_suffix}")
    elif task_result.issue_title:
        console.print(f"Task:   {task_result.issue_title}")
    if task_result.issue_state:
        console.print(f"Issue:  {str(task_result.issue_state).lower()}")
    if task_result.related_issue_numbers:
        console.print(
            "Related Issue(s): "
            + "  ".join(f"#{number}" for number in task_result.related_issue_numbers)
        )
    if task_result.dependency_issue_numbers:
        console.print(
            "Dependencies: "
            + "  ".join(f"#{number}" for number in task_result.dependency_issue_numbers)
        )
    if task.spec_ref:
        console.print(f"Spec Ref: {task.spec_ref}")
    if task.latest_verdict:
        v = task.latest_verdict
        color = {
            "PASS": "green",
            "MAJOR": "yellow",
            "BLOCK": "red",
        }.get(v.verdict, "cyan")
        console.print(f"Verdict: [{color}]{v.verdict}[/] ({v.actor})")
    if task.next_step:
        console.print(f"Next Step: {task.next_step}")
    if task.blocked_by:
        console.print(f"Blocked By: {task.blocked_by}")

    if task_result.latest_ref:
        latest_ref = task_result.latest_ref
        worktree_root = task.worktree_root if hasattr(task, "worktree_root") else None
        display_ref = resolve_ref_path(latest_ref.ref, worktree_root)
        ref_cmd = ref_to_handoff_cmd(display_ref, task.branch)
        console.print("\n[bold]Latest Work[/]")
        console.print(f"Ref:     {latest_ref.kind}  {ref_cmd}")

        # Show only first 3 lines of summary for readability
        if latest_ref.summary:
            summary_lines = latest_ref.summary.strip().split("\n")[:3]
            console.print("Summary:")
            for line in summary_lines:
                console.print(f"  {line}")

    # Comments will be shown via render_task_comments(), not here
    # Removed: Latest Instruction/Comment section (consolidated into comments view)

    if task_result.pr_summary:
        pr = task_result.pr_summary
        draft_suffix = " draft" if pr.draft else ""
        console.print("\n[bold]PR / CI[/]")
        console.print(f"PR:      #{pr.number}  {pr.state}{draft_suffix}  {pr.title}")
        if pr.checks:
            console.print(f"Checks:  {pr.checks}")
        console.print(f"URL:     {pr.url}")


def render_task_comments(issue: dict[str, object], max_comments: int = 3) -> None:
    """Render last N comments with human/agent labels.

    Args:
        issue: Issue dict with comments
        max_comments: Maximum number of recent comments to show (default 3)
    """
    comments = issue.get("comments") or []
    if not isinstance(comments, list):
        comments = []

    if not comments:
        console.print("\n[dim]No comments found.[/]")
        return

    # Get last N comments
    recent_comments = (
        comments[-max_comments:] if len(comments) > max_comments else comments
    )

    total = len(comments)
    shown = len(recent_comments)
    console.print(f"\n[bold]Recent Comments (last {shown} of {total})[/]\n")

    for idx, comment in enumerate(recent_comments):
        if not isinstance(comment, dict):
            continue

        body = str(comment.get("body") or "").strip()
        author = comment.get("author") or {}
        login = str(author.get("login") or "unknown").strip()

        # Find automation marker if present (supports `### [marker]` format)
        marker = None
        escaped_markers = [re.escape(m) for m in AUTOMATED_MARKERS]
        pattern = r"^(\s*|#{1,6}\s*)(" + "|".join(escaped_markers) + ")"
        match = re.match(pattern, body, re.IGNORECASE)
        if match:
            marker = match.group(2)  # Group 2 is the marker

        # Display with label
        if marker:
            label = marker.strip("[]")
            console.print(f"[bold yellow]\\[{label}][/bold yellow]")
        else:
            # Bug 4: Human comments label
            console.print(f"[bold cyan]\\[user:{login}][/bold cyan]")

        # Only truncate if NOT the last comment (most recent)
        # Last comment should be shown in full for agent context
        is_last = idx == len(recent_comments) - 1
        if not is_last and len(body) > 300:
            body = body[:300] + "..."

        console.print(body)
        console.print()  # Empty line between comments


def render_task_search(
    results: list[dict[str, object]],
    query: str,
    json_output: bool = False,
) -> None:
    """Render task search results.

    Args:
        results: List of issue dicts from search
        query: The search query string
        json_output: If True, output as JSON; otherwise formatted table
    """
    if json_output:
        console.print(
            json.dumps(results, indent=2, default=str),
            markup=False,
            highlight=False,
            soft_wrap=True,
        )
        return

    # Human-readable format
    count = len(results)
    console.print(f'\n[bold]Found {count} issue(s) matching "{query}":[/]\n')

    if not results:
        return

    for issue in results:
        if not isinstance(issue, dict):
            continue

        number = issue.get("number")
        title = issue.get("title", "")
        state = str(issue.get("state", "OPEN")).upper()

        # State color
        state_color = "green" if state == "OPEN" else "red"

        # Format: #237  [OPEN]   Split review/plan/run agent contracts...
        console.print(
            f"  [bold]#{number}[/]  [{state_color}][{state}][/{state_color}]   {title}"
        )

    console.print()  # Empty line at end
