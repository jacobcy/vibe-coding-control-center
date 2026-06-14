"""Task UI rendering."""

import json
import re
from dataclasses import asdict
from types import ModuleType

from vibe3.services.shared import ref_to_handoff_cmd
from vibe3.services.task import TaskShowResult
from vibe3.ui.console_impl import console
from vibe3.ui.flow_ui_primitives import resolve_ref_path
from vibe3.utils import AUTOMATED_MARKERS

# Display limits for task show output
MAX_SUMMARY_LINES = 3  # Maximum summary lines shown in non-full mode
MAX_COMMENTS_DISPLAY = 3  # Maximum recent comments to display


def _get_yaml() -> ModuleType:
    """Lazy import yaml to avoid unconditional import cost."""
    import yaml

    return yaml


def build_task_show_payload(task_result: "TaskShowResult") -> dict[str, object]:
    """Build a single JSON payload for task show."""
    return task_result.to_payload()  # type: ignore[no-any-return]


def render_task_show(
    task_result: "TaskShowResult",
    output_format: str,
    full: bool = False,
) -> None:
    """Render task show output.

    Args:
        task_result: Task show query result
        output_format: Output format (json, yaml, or table)
        full: If True, show complete summary without truncation (table mode only)
    """
    # Handle case where no flow exists
    if not task_result.local_task:
        # Check if branch is an issue number - try to show basic issue info
        branch = task_result.branch
        if branch.isdigit():
            # Branch is an issue number without flow
            # Try to fetch and display basic issue info
            if task_result.issue_title or task_result.issue_state:
                pr_data = (
                    asdict(task_result.pr_summary) if task_result.pr_summary else None
                )
                if output_format == "json":
                    console.print(
                        json.dumps(
                            {
                                "branch": branch,
                                "issue_number": int(branch),
                                "title": task_result.issue_title,
                                "state": task_result.issue_state,
                                "pr": pr_data,
                            },
                            indent=2,
                            default=str,
                        ),
                        markup=False,
                    )
                elif output_format == "yaml":
                    console.print(
                        _get_yaml().dump(
                            {
                                "branch": branch,
                                "issue_number": int(branch),
                                "title": task_result.issue_title,
                                "state": task_result.issue_state,
                                "pr": pr_data,
                            },
                            default_flow_style=False,
                            allow_unicode=True,
                        ),
                        markup=False,
                    )
                else:
                    console.print(f"Remote issue #{branch} (no local flow)")
                    console.print()
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
            if output_format in ("json", "yaml"):
                output_data = {"branch": branch, "error": "No flow found"}
                if output_format == "json":
                    console.print(json.dumps(output_data), markup=False)
                else:
                    console.print(
                        _get_yaml().dump(output_data, default_flow_style=False),
                        markup=False,
                    )
            else:
                console.print(f"[yellow]No flow found for issue #{branch}[/]")
                console.print("Tip: Use 'vibe3 flow update' to register current branch")
            return
        # Non-numeric branch without flow
        if output_format in ("json", "yaml"):
            output_data = {"branch": branch, "error": "No flow found"}
            if output_format == "json":
                console.print(json.dumps(output_data), markup=False)
            else:
                console.print(
                    _get_yaml().dump(output_data, default_flow_style=False),
                    markup=False,
                )
        else:
            console.print(f"[yellow]No flow found: {branch}[/]")
        return

    task = task_result.local_task
    if output_format == "json":
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

    if output_format == "yaml":
        console.print(
            _get_yaml().dump(
                build_task_show_payload(task_result),
                default_flow_style=False,
                allow_unicode=True,
            ),
            markup=False,
        )
        return

    # Table format (default)
    console.print("[bold]Current Task[/]")
    console.print(f"Branch: {task.branch}")
    console.print(f"Flow:   {task.flow_slug} ({task.flow_status})")

    # Display task issues (primary + additional)
    if task_result.task_issue_numbers and len(task_result.task_issue_numbers) > 1:
        # Multiple task issues: show as list
        console.print("\n[bold]Task Issue(s):[/]")
        for idx, issue_num in enumerate(task_result.task_issue_numbers):
            if idx == 0:
                label = "primary"
                title_suffix = (
                    f"  {task_result.issue_title}" if task_result.issue_title else ""
                )
                console.print(f"  #{issue_num}  ({label}){title_suffix}")
            else:
                console.print(f"  #{issue_num}")
    else:
        # Single or no task_issue_numbers: use existing format
        if task.task_issue_number:
            title_suffix = (
                f"  {task_result.issue_title}" if task_result.issue_title else ""
            )
            console.print(f"Task:   #{task.task_issue_number}{title_suffix}")
        elif task_result.issue_title:
            console.print(f"Task:   {task_result.issue_title}")

    if task_result.issue_state:
        console.print(f"Issue:  {str(task_result.issue_state).lower()}")

    # Group linked issues under a sub-header
    has_linked = (
        task_result.related_issue_numbers or task_result.dependency_issue_numbers
    )
    if has_linked:
        console.print("\n[bold]Linked Issues[/]")
        if task_result.related_issue_numbers:
            related = "  ".join(
                f"#{number}" for number in task_result.related_issue_numbers
            )
            console.print(f"Related Issue(s): {related}")
        if task_result.dependency_issue_numbers:
            deps = "  ".join(
                f"#{number}" for number in task_result.dependency_issue_numbers
            )
            console.print(f"Dependencies: {deps}")
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
    if task.blocked_reason:
        console.print(f"Blocked Reason: {task.blocked_reason}")

    if task_result.latest_ref:
        latest_ref = task_result.latest_ref
        worktree_root = task.worktree_root if hasattr(task, "worktree_root") else None
        display_ref = resolve_ref_path(latest_ref.ref, worktree_root)
        ref_field = f"{latest_ref.kind}_ref"
        ref_cmd = ref_to_handoff_cmd(display_ref, task.branch, ref_field)
        console.print("\n[bold]Latest Work[/]")
        console.print(f"Ref:     {latest_ref.kind}  {ref_cmd}")

        # Show summary (full or truncated)
        if latest_ref.summary:
            summary_lines = latest_ref.summary.strip().split("\n")
            if full:
                # Show complete summary
                console.print("Summary:")
                for line in summary_lines:
                    console.print(f"  {line}")
            else:
                # Show only first N lines for readability
                summary_lines = summary_lines[:MAX_SUMMARY_LINES]
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


def render_task_comments(
    issue: dict[str, object], max_comments: int = MAX_COMMENTS_DISPLAY
) -> None:
    """Render issue body and last N comments with human/agent labels.

    Args:
        issue: Issue dict with body and comments
        max_comments: Maximum number of recent comments to show
    """
    # Display issue body first
    body = str(issue.get("body") or "").strip()
    if body:
        console.print("\n[bold]Issue Body[/]\n")
        console.print(body)

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

    for comment in recent_comments:
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

        # Show full comment body without truncation
        console.print(body)
        console.print()  # Empty line between comments
