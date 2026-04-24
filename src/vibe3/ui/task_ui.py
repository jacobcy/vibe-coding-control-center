"""Task UI rendering."""

import json
from typing import TYPE_CHECKING

from vibe3.services.task_service import is_human_comment
from vibe3.ui.console import console

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
    if not task_result.local_task:
        console.print(f"[red]Task not found: {task_result.branch}[/]")
        raise SystemExit(1)

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
        console.print("\n[bold]Latest Work[/]")
        console.print(f"Ref:     {latest_ref.kind}  {latest_ref.ref}")
        console.print(f"Summary: {latest_ref.summary}")

    instruction = task_result.latest_human_instruction or task_result.latest_comment
    if instruction:
        label = (
            "Latest Instruction"
            if task_result.latest_human_instruction is not None
            else "Latest Comment"
        )
        console.print(f"\n[bold]{label}[/]")
        console.print(f"Author:  {instruction.author}")
        console.print(f"Summary: {instruction.body}")

    if task_result.pr_summary:
        pr = task_result.pr_summary
        draft_suffix = " draft" if pr.draft else ""
        console.print("\n[bold]PR / CI[/]")
        console.print(f"PR:      #{pr.number}  {pr.state}{draft_suffix}  {pr.title}")
        if pr.checks:
            console.print(f"Checks:  {pr.checks}")
        console.print(f"URL:     {pr.url}")


def render_task_comments(issue: dict[str, object]) -> None:
    """Render full latest comments for comment-focused inspection."""
    comments = issue.get("comments") or []
    if not isinstance(comments, list):
        comments = []

    latest_comment = comments[-1] if comments else None
    latest_human = next(
        (
            comment
            for comment in reversed(comments)
            if isinstance(comment, dict) and is_human_comment(comment)
        ),
        None,
    )

    console.print("\n[bold]Latest Comment[/]")
    if isinstance(latest_comment, dict):
        author = str((latest_comment.get("author") or {}).get("login") or "unknown")
        console.print(f"Author:  {author}")
        body = str(latest_comment.get("body") or "").strip()
        console.print(body or "(empty)")
    else:
        console.print("(no comments)")

    console.print("\n[bold]Latest Human Instruction[/]")
    if isinstance(latest_human, dict):
        author = str((latest_human.get("author") or {}).get("login") or "unknown")
        console.print(f"Author:  {author}")
        body = str(latest_human.get("body") or "").strip()
        console.print(body or "(empty)")
    else:
        console.print("(no human comments)")
