#!/usr/bin/env python3
"""Task command handlers."""

from contextlib import contextmanager
from typing import Annotated, Iterator

import typer

from vibe3.observability.logger import setup_logging
from vibe3.observability.trace import trace_context
from vibe3.services.flow_service import FlowService
from vibe3.services.milestone_service import MilestoneService
from vibe3.services.task_service import TaskService
from vibe3.services.task_usecase import TaskUsecase
from vibe3.ui.task_ui import (
    render_task_show_error_with_milestone,
    render_task_show_with_milestone,
)

app = typer.Typer(
    help="Manage execution tasks", no_args_is_help=True, rich_markup_mode="rich"
)


@contextmanager
def _noop() -> Iterator[None]:
    yield


def _build_task_usecase() -> TaskUsecase:
    """Construct a task usecase with command-local service wiring."""
    return TaskUsecase(
        flow_service=FlowService(),
        task_service=TaskService(),
    )


def _build_milestone_service() -> MilestoneService:
    """Construct a milestone service."""
    return MilestoneService()


@app.command()
def list(
    trace: Annotated[bool, typer.Option("--trace")] = False,
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """List all tasks (flows with task issue bound)."""
    import json

    if trace:
        setup_logging(verbose=2)

    usecase = _build_task_usecase()

    task_rows = usecase.list_task_rows()
    if not task_rows:
        typer.echo("No tasks found")
        return
    if json_output:
        typer.echo(
            json.dumps([row.__dict__ for row in task_rows], indent=2, default=str)
        )
        return
    for task_flow in task_rows:
        typer.echo(
            f"  #{task_flow.task_issue_number}  {task_flow.flow_slug}  "
            f"{task_flow.flow_status}  branch={task_flow.branch}"
        )


@app.command()
def show(
    branch: Annotated[str | None, typer.Argument(help="Branch name")] = None,
    trace: Annotated[bool, typer.Option("--trace")] = False,
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Show task details, including remote GitHub Project fields."""
    usecase = _build_task_usecase()
    milestone_svc = _build_milestone_service()

    try:
        target_branch = usecase.resolve_branch(branch)
    except RuntimeError as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(1) from error

    if trace:
        setup_logging(verbose=2)

    ctx = (
        trace_context(command="task show", domain="task", branch=target_branch)
        if trace
        else _noop()
    )
    with ctx:
        task_result = usecase.show_task(target_branch)

        # Fetch milestone context if task has an issue number
        milestone_ctx = None
        issue_number = None
        if task_result.view and task_result.view.task_issue_number:
            issue_number = task_result.view.task_issue_number.value
        elif task_result.local_task and task_result.local_task.task_issue_number:
            issue_number = task_result.local_task.task_issue_number

        if issue_number:
            milestone_ctx = milestone_svc.get_milestone_context(issue_number)

        # Delegate rendering to UI layer
        if task_result.hydrate_error:
            render_task_show_error_with_milestone(
                task_result, milestone_ctx, json_output
            )
        else:
            render_task_show_with_milestone(task_result, milestone_ctx, json_output)
