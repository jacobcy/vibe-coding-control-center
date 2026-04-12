"""Task UI rendering."""

import json
from typing import TYPE_CHECKING

from vibe3.clients.github_issues_ops import MilestoneContext
from vibe3.ui.console import console
from vibe3.ui.flow_ui import render_milestone

if TYPE_CHECKING:
    from vibe3.services.task_service import TaskShowResult


def render_task_milestone(
    task_issue_number: int, milestone_data: dict | MilestoneContext
) -> None:
    """Render milestone orchestration context for a task."""
    if isinstance(milestone_data, MilestoneContext):
        milestone_data = {
            "number": milestone_data.number,
            "title": milestone_data.title,
            "open": milestone_data.open_count,
            "closed": milestone_data.closed_count,
            "issues": milestone_data.issues,
            "task_issue": milestone_data.task_issue_number,
        }
    render_milestone(milestone_data, task_issue_number)


def render_task_show(task_result: "TaskShowResult", json_output: bool) -> None:
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
        console.print(json.dumps(task.model_dump(), indent=2, default=str))
        return

    console.print(f"Branch: {task.branch}")
    console.print(f"Flow:   {task.flow_slug} ({task.flow_status})")

    if task.task_issue_number:
        console.print(f"Task Issue: #{task.task_issue_number}")
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
    if task.next_step:
        console.print(f"Next Step: {task.next_step}")
    if task.blocked_by:
        console.print(f"Blocked By: {task.blocked_by}")


def render_task_show_with_milestone(
    task_result: "TaskShowResult",
    milestone_ctx: MilestoneContext | None,
    json_output: bool,
) -> None:
    """Render task show output with milestone context."""
    render_task_show(task_result, json_output)

    if not json_output and milestone_ctx and task_result.local_task:
        task_issue = task_result.local_task.task_issue_number
        if task_issue:
            console.print("\n[bold]Orchestration Context (Milestone)[/]")
            render_task_milestone(task_issue, milestone_ctx)
