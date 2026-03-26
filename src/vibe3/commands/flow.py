#!/usr/bin/env python3
"""Flow command handlers."""

import json
from contextlib import nullcontext
from typing import Annotated, Literal

import typer
from loguru import logger

from vibe3.clients.git_client import GitClient
from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.commands.flow_lifecycle import aborted, blocked, done, switch
from vibe3.models.project_item import LinkError
from vibe3.observability.logger import setup_logging
from vibe3.observability.trace import trace_context
from vibe3.services.flow_service import FlowService
from vibe3.services.handoff_service import HandoffService
from vibe3.services.task_service import TaskService
from vibe3.ui.console import console
from vibe3.ui.flow_ui import (
    render_flow_created,
    render_flow_status,
    render_flow_status_table,
    render_flow_timeline,
    render_flows_table,
)

app = typer.Typer(
    help=(
        "Manage logic flows (branch-centric: flows are automatically created "
        "and managed based on git branches)"
    ),
    no_args_is_help=True,
    rich_markup_mode="rich",
)


def _trace_scope(trace: bool, command: str, **kwargs: str):  # type: ignore[no-untyped-def]
    if trace:
        setup_logging(verbose=2)
        return trace_context(command=command, domain="flow", **kwargs)
    return nullcontext()


def _parse_issue_number(task_ref: str) -> int:
    digits = "".join(filter(str.isdigit, task_ref))
    if not digits:
        raise ValueError(f"Invalid task ID format: {task_ref}")
    return int(digits)


def _bind_task_to_flow(
    branch: str,
    task_ref: str,
    actor: str,
    command: str,
) -> int:
    issue_number = _parse_issue_number(task_ref)
    store = SQLiteClient()

    store.add_issue_link(branch, issue_number, "task")
    store.update_flow_state(branch, task_issue_number=issue_number)
    store.add_event(branch, "task_bound", actor, detail=f"Task bound: {task_ref}")
    logger.bind(command=command, task=task_ref).info("Task bound to flow")

    # 自动将 issue 加入 GitHub Project（链式反应，非致命）
    link_result = TaskService().auto_link_issue_to_project(branch, issue_number)
    if isinstance(link_result, LinkError):
        logger.bind(command=command, task=task_ref).warning(
            f"Auto project link skipped: {link_result.message}"
        )

    return issue_number


@app.command(name="add")
def add(
    name: Annotated[str, typer.Argument(help="Flow name")],
    task: Annotated[str | None, typer.Option(help="Task ID to bind")] = None,
    spec: Annotated[str | None, typer.Option("--spec", help="Spec file path")] = None,
    force: Annotated[
        bool,
        typer.Option("--yes", "-y", help="Force add on branch with existing flow"),
    ] = False,
    trace: Annotated[
        bool, typer.Option("--trace", help="启用调用链路追踪 + DEBUG 日志")
    ] = False,
    json_output: Annotated[bool, typer.Option("--json", help="JSON 格式输出")] = False,
) -> None:
    """Add flow to current branch.

    This command registers a flow on the current branch.
    Use 'flow create' to create a new branch with flow.

    If current branch already has a flow:
    - Active/blocked flow: Error (use --yes to force)
    - Done/aborted/stale flow: Warning, then proceed

    Examples:
        vibe3 flow add my-feature
        vibe3 flow add my-feature --yes  # Force add on branch with active flow
    """
    with _trace_scope(trace, "flow add", name=name):
        logger.bind(command="flow add", name=name, task=task).info("Adding flow")

        git = GitClient()
        service = FlowService()
        branch = git.get_current_branch()

        # Check if flow already exists
        existing_flow = service.get_flow_status(branch)
        if existing_flow:
            status = existing_flow.flow_status

            # Active/blocked flow: block add
            if status in ["active", "blocked"]:
                if not force:
                    console.print(
                        f"[red]Error: Branch '{branch}' has active flow: "
                        f"{existing_flow.flow_slug}[/]"
                    )
                    console.print(
                        "[yellow]Use --yes to force add, "
                        "or switch to another branch first[/]"
                    )
                    raise typer.Exit(1)

            # Done/aborted/stale flow: allow add with warning
            if status in ["done", "aborted", "stale"] and not force:
                console.print(
                    f"[yellow]Warning: Branch '{branch}' has completed flow: "
                    f"{existing_flow.flow_slug}[/]"
                )
                console.print("[yellow]Adding new flow to this branch[/]")

        # Register flow
        flow = service.create_flow(slug=name, branch=branch)

        # Bind task if provided
        if task:
            try:
                _bind_task_to_flow(branch, task, "system", command="flow add")
            except ValueError:
                logger.bind(command="flow add", task=task).warning(
                    "Invalid task ID format, skipping binding"
                )

        # Bind spec_ref if provided
        if spec:
            store = SQLiteClient()
            store.update_flow_state(branch, spec_ref=spec, latest_actor="system")
            store.add_event(
                branch, "spec_bound", "system", detail=f"Spec bound: {spec}"
            )
            logger.bind(command="flow add", spec=spec).info("Spec bound to flow")

        # Auto-initialize handoff current.md
        HandoffService().ensure_current_handoff()

        if json_output:
            typer.echo(json.dumps(flow.model_dump(), indent=2, default=str))
        else:
            render_flow_created(flow, task)


# Backward compatibility alias for 'flow new'
@app.command(name="new", deprecated=True, hidden=True)
def new(
    name: Annotated[str, typer.Argument(help="Flow name")],
    task: Annotated[str | None, typer.Option(help="Task ID to bind")] = None,
    spec: Annotated[str | None, typer.Option("--spec", help="Spec file path")] = None,
    force: Annotated[
        bool,
        typer.Option("--yes", "-y", help="Force add on branch with existing flow"),
    ] = False,
    trace: Annotated[
        bool, typer.Option("--trace", help="启用调用链路追踪 + DEBUG 日志")
    ] = False,
    json_output: Annotated[bool, typer.Option("--json", help="JSON 格式输出")] = False,
) -> None:
    """Deprecated: Use 'flow add' instead.

    This command is kept for backward compatibility.
    It will be removed in a future version.
    """
    console.print(
        "[yellow]Warning: 'flow new' is deprecated. Use 'flow add' instead.[/]"
    )
    add(name, task, spec, force, trace, json_output)


@app.command(name="create")
def create(
    name: Annotated[str, typer.Argument(help="Flow name")],
    task: Annotated[str | None, typer.Option(help="Task ID to bind")] = None,
    spec: Annotated[str | None, typer.Option("--spec", help="Spec file path")] = None,
    base: Annotated[
        str,
        typer.Option(
            "--base",
            "-b",
            help="Base branch (default: main, also supports 'current' or branch name)",
        ),
    ] = "main",
    trace: Annotated[
        bool, typer.Option("--trace", help="启用调用链路追踪 + DEBUG 日志")
    ] = False,
    json_output: Annotated[bool, typer.Option("--json", help="JSON 格式输出")] = False,
) -> None:
    """Create new branch with flow.

    This command creates a new branch and registers a flow on it.

    Base branch options:
    - main (default): Create from origin/main
    - current: Create from current branch
    - <branch-name>: Create from specified branch

    Examples:
        vibe3 flow create my-feature
        vibe3 flow create my-feature --base main
        vibe3 flow create my-feature --base current
        vibe3 flow create my-feature --base feature/A
    """
    with _trace_scope(trace, "flow create", name=name, base=base):
        logger.bind(command="flow create", name=name, base=base, task=task).info(
            "Creating flow with new branch"
        )

        git = GitClient()
        service = FlowService()

        # Determine base branch
        if base == "main":
            start_ref = "origin/main"
        elif base == "current":
            start_ref = git.get_current_branch()
        else:
            # User-specified branch name
            start_ref = base

        # Check if branch already exists
        branch_name = f"task/{name}"
        if git.branch_exists(branch_name):
            console.print(f"[red]Error: Branch '{branch_name}' already exists.[/]")
            console.print(
                f"[yellow]Hint: Use different name or 'vibe3 flow switch {name}'[/]"
            )
            raise typer.Exit(1)

        # Create branch and register flow
        try:
            flow = service.create_flow_with_branch(slug=name, start_ref=start_ref)
        except RuntimeError as e:
            console.print(f"[red]Error: {e}[/]")
            raise typer.Exit(1)

        # Bind task if provided
        if task:
            try:
                _bind_task_to_flow(branch_name, task, "system", command="flow create")
            except ValueError:
                logger.bind(command="flow create", task=task).warning(
                    "Invalid task ID format, skipping binding"
                )

        # Bind spec_ref if provided
        if spec:
            store = SQLiteClient()
            store.update_flow_state(branch_name, spec_ref=spec, latest_actor="system")
            store.add_event(
                branch_name, "spec_bound", "system", detail=f"Spec bound: {spec}"
            )
            logger.bind(command="flow create", spec=spec).info("Spec bound to flow")

        # Auto-initialize handoff current.md
        HandoffService().ensure_current_handoff()

        if json_output:
            typer.echo(json.dumps(flow.model_dump(), indent=2, default=str))
        else:
            render_flow_created(flow, task)


@app.command()
def bind(
    task_id: Annotated[str, typer.Argument(help="Task ID to bind")],
    actor: Annotated[str, typer.Option(help="Actor binding the task")] = "system",
    trace: Annotated[
        bool, typer.Option("--trace", help="启用调用链路追踪 + DEBUG 日志")
    ] = False,  # noqa: E501
    json_output: Annotated[bool, typer.Option("--json", help="JSON 格式输出")] = False,
) -> None:
    """Bind a task to current flow."""
    with _trace_scope(trace, "flow bind", task_id=task_id):
        logger.bind(command="flow bind", task_id=task_id, actor=actor).info(
            "Binding task to flow"
        )

        git = GitClient()
        branch = git.get_current_branch()

        try:
            _bind_task_to_flow(branch, task_id, actor, command="flow bind")

            if json_output:
                typer.echo(json.dumps({"status": "bound", "task_id": task_id}))
            else:
                console.print(f"[green]✓[/] Task {task_id} bound to flow {branch}")
        except ValueError:
            logger.error(f"Invalid task ID format: {task_id}")
            raise typer.BadParameter(f"Invalid task ID format: {task_id}")


@app.command()
def show(
    flow_name: Annotated[
        str | None, typer.Argument(help="Branch name (defaults to current branch)")
    ] = None,
    snapshot: Annotated[bool, typer.Option("--snapshot", help="静态快照模式")] = False,
    trace: Annotated[
        bool, typer.Option("--trace", help="启用调用链路追踪 + DEBUG 日志")
    ] = False,  # noqa: E501
    json_output: Annotated[bool, typer.Option("--json", help="JSON 格式输出")] = False,
) -> None:
    """Show flow details for a branch."""
    with _trace_scope(trace, "flow show"):
        logger.bind(command="flow show", flow_name=flow_name).info(
            "Showing flow details"
        )

        git = GitClient()
        service = FlowService()
        branch = flow_name if flow_name else git.get_current_branch()

        if snapshot:
            flow_status = service.get_flow_status(branch)
            if not flow_status:
                logger.error(f"Flow not found: {branch}")
                raise typer.Exit(1)
            render_flow_status(flow_status)
            return

        timeline = service.get_flow_timeline(branch)
        if not timeline["state"]:
            logger.error(f"Flow not found: {branch}")
            raise typer.Exit(1)

        if json_output:
            output = {
                "state": timeline["state"].model_dump(),
                "events": [e.model_dump() for e in timeline["events"]],
            }
            typer.echo(json.dumps(output, indent=2, default=str))
        else:
            render_flow_timeline(timeline["state"], timeline["events"])


@app.command()
def status(
    json_output: Annotated[bool, typer.Option("--json", help="JSON output")] = False,
    trace: Annotated[
        bool, typer.Option("--trace", help="启用调用链路追踪 + DEBUG 日志")
    ] = False,  # noqa: E501
) -> None:
    """Show flow status."""
    with _trace_scope(trace, "flow status"):
        logger.bind(command="flow status", json_output=json_output).info(
            "Getting flow status"
        )

        git = GitClient()
        service = FlowService()
        branch = git.get_current_branch()
        flow_status = service.get_flow_status(branch)

        if json_output:
            output = flow_status.model_dump() if flow_status else {}
            typer.echo(json.dumps(output, indent=2, default=str))
        else:
            if not flow_status:
                logger.info("No active flow on current branch")
                raise typer.Exit(0)
            render_flow_status_table(flow_status)


@app.command()
def list(
    status_filter: Annotated[
        Literal["active", "blocked", "done", "stale"] | None,
        typer.Option("--status", help="Filter by status"),
    ] = None,
    trace: Annotated[
        bool, typer.Option("--trace", help="启用调用链路追踪 + DEBUG 日志")
    ] = False,  # noqa: E501
    json_output: Annotated[bool, typer.Option("--json", help="JSON 格式输出")] = False,
) -> None:
    """List all flows."""
    with _trace_scope(trace, "flow list"):
        logger.bind(command="flow list", status_filter=status_filter).info(
            "Listing flows"
        )

        service = FlowService()
        flows = service.list_flows(status=status_filter)

        if not flows:
            logger.info("No flows found")
            raise typer.Exit(0)

        if json_output:
            typer.echo(
                json.dumps([f.model_dump() for f in flows], indent=2, default=str)
            )
        else:
            render_flows_table(flows)


# Register lifecycle commands from flow_lifecycle.py
app.command(name="switch")(switch)
app.command(name="done")(done)
app.command(name="blocked")(blocked)
app.command(name="aborted")(aborted)
