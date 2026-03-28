#!/usr/bin/env python3
"""Task command handlers."""

import json
from contextlib import contextmanager
from typing import Annotated, Iterator

import typer

from vibe3.observability.logger import setup_logging
from vibe3.observability.trace import trace_context
from vibe3.services.flow_service import FlowService
from vibe3.services.task_service import TaskService
from vibe3.services.task_usecase import TaskShowResult, TaskUsecase

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


@app.command()
def list(
    trace: Annotated[bool, typer.Option("--trace")] = False,
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """List all tasks (flows with task issue bound)."""
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
        _render_task_show(task_result, json_output)


def _render_task_show(task_result: TaskShowResult, json_output: bool) -> None:
    """Render task show output while keeping show() thin."""
    if task_result.hydrate_error:
        _render_task_show_error(task_result, json_output)
        return
    if not task_result.view:
        typer.echo(f"Task not found: {task_result.branch}", err=True)
        raise typer.Exit(1)
    view = task_result.view
    if json_output:
        typer.echo(json.dumps(view.model_dump(), indent=2, default=str))
        return

    bound_id = view.project_item_id.value if view.project_item_id else None
    bind_status = "[bound]" if bound_id else "[unbound]"
    typer.echo(f"Branch: {view.branch}")
    typer.echo(f"Project Item {bind_status}: {bound_id or 'N/A'}")

    if view.task_issue_number:
        typer.echo(f"Task Issue: #{view.task_issue_number.value}")
    if task_result.related_issue_numbers:
        typer.echo(
            "Related Issue(s): "
            + "  ".join(f"#{number}" for number in task_result.related_issue_numbers)
        )
    if task_result.dependency_issue_numbers:
        typer.echo(
            "Dependencies: "
            + "  ".join(f"#{number}" for number in task_result.dependency_issue_numbers)
        )
    if view.spec_ref:
        typer.echo(f"Spec Ref: {view.spec_ref.value}")
    if view.next_step:
        typer.echo(f"Next Step: {view.next_step.value}")
    if view.blocked_by:
        typer.echo(f"Blocked By: {view.blocked_by.value}")

    if view.offline_mode:
        typer.echo("[offline mode] 远端读取失败，仅显示本地 bridge 字段")
    else:
        if view.title:
            typer.echo(f"[remote] Title:    {view.title.value}")
        if view.status:
            typer.echo(f"[remote] Status:   {view.status.value}")
        if view.priority:
            typer.echo(f"[remote] Priority: {view.priority.value}")
        if view.assignees:
            typer.echo(f"[remote] Assignees: {', '.join(view.assignees.value)}")

    if view.identity_drift:
        typer.echo("[warning] identity_drift=True: 本地与远端 identity 不一致")


def _render_task_show_error(task_result: TaskShowResult, json_output: bool) -> None:
    """Render hydrate fallback or hard error for task show."""
    error = task_result.hydrate_error
    if not error:
        return
    if error.type == "binding_invalid":
        typer.echo(f"Error [{error.type}]: {error.message}", err=True)
        raise typer.Exit(1)
    task = task_result.local_task
    if not task:
        typer.echo(f"Task not found: {task_result.branch}", err=True)
        raise typer.Exit(1)
    if json_output:
        typer.echo(json.dumps(task.model_dump(), indent=2, default=str))
        return
    typer.echo(f"Branch: {task.branch}")
    if task.task_issue_number:
        typer.echo(f"Task Issue: #{task.task_issue_number}")
    typer.echo(f"Status (local flow): {task.flow_status}")
    typer.echo("未绑定 task，请先运行 vibe3 flow bind <issue_number> 绑定 task。")
