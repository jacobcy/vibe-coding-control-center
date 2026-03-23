#!/usr/bin/env python3
"""Flow command handlers."""

import json
from contextlib import contextmanager
from typing import Annotated, Iterator, Literal

import typer
from loguru import logger

from vibe3.clients.git_client import GitClient
from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.observability.logger import setup_logging
from vibe3.observability.trace import trace_context
from vibe3.services.flow_service import FlowService
from vibe3.ui.flow_ui import (
    render_flow_created,
    render_flow_status,
    render_flow_status_table,
    render_flow_timeline,
    render_flows_table,
)

app = typer.Typer(
    help="Manage logic flows (branch-centric)",
    no_args_is_help=True,
    rich_markup_mode="rich",
)


@contextmanager
def _noop() -> Iterator[None]:
    yield


@app.command()
def new(
    name: Annotated[str, typer.Argument(help="Flow name")],
    task: Annotated[str | None, typer.Option(help="Task ID to bind")] = None,
    spec: Annotated[str | None, typer.Option("--spec", help="Spec file path")] = None,
    actor: Annotated[str, typer.Option(help="Actor creating the flow")] = "claude",
    trace: Annotated[
        bool, typer.Option("--trace", help="启用调用链路追踪 + DEBUG 日志")
    ] = False,  # noqa: E501
    json_output: Annotated[bool, typer.Option("--json", help="JSON 格式输出")] = False,
) -> None:
    """Create a new flow."""
    if trace:
        setup_logging(verbose=2)

    ctx = (
        trace_context(command="flow new", domain="flow", name=name)
        if trace
        else _noop()
    )
    with ctx:
        logger.bind(command="flow new", name=name, task=task, actor=actor).info(
            "Creating new flow"
        )

        git = GitClient()
        service = FlowService()
        branch = git.get_current_branch()
        flow = service.create_flow(slug=name, branch=branch)

        # Bind task if provided
        if task:
            store = SQLiteClient()
            try:
                issue_number = int("".join(filter(str.isdigit, task)))
                store.add_issue_link(branch, issue_number, "task")
                store.update_flow_state(branch, task_issue_number=issue_number)
                store.add_event(
                    branch, "task_bound", actor, detail=f"Task bound: {task}"
                )
                logger.bind(command="flow new", task=task).info("Task bound to flow")
            except ValueError:
                logger.bind(command="flow new", task=task).warning(
                    "Invalid task ID format, skipping binding"
                )

        # Bind spec_ref if provided
        if spec:
            store = SQLiteClient()
            store.update_flow_state(branch, spec_ref=spec, latest_actor=actor)
            store.add_event(branch, "spec_bound", actor, detail=f"Spec bound: {spec}")
            logger.bind(command="flow new", spec=spec).info("Spec bound to flow")

        if json_output:
            typer.echo(json.dumps(flow.model_dump(), indent=2, default=str))
        else:
            render_flow_created(flow, task)


@app.command()
def bind(
    task_id: Annotated[str, typer.Argument(help="Task ID to bind")],
    actor: Annotated[str, typer.Option(help="Actor binding the task")] = "claude",
    trace: Annotated[
        bool, typer.Option("--trace", help="启用调用链路追踪 + DEBUG 日志")
    ] = False,  # noqa: E501
    json_output: Annotated[bool, typer.Option("--json", help="JSON 格式输出")] = False,
) -> None:
    """Bind a task to current flow."""
    if trace:
        setup_logging(verbose=2)

    ctx = (
        trace_context(command="flow bind", domain="flow", task_id=task_id)
        if trace
        else _noop()
    )
    with ctx:
        logger.bind(command="flow bind", task_id=task_id, actor=actor).info(
            "Binding task to flow"
        )

        # TODO: Implement bind_flow in FlowService
        raise NotImplementedError(
            "bind_flow not yet implemented. Use task bind command instead."
        )


@app.command()
def show(
    flow_name: Annotated[str | None, typer.Argument(help="Flow to show")] = None,
    snapshot: Annotated[bool, typer.Option("--snapshot", help="静态快照模式")] = False,
    trace: Annotated[
        bool, typer.Option("--trace", help="启用调用链路追踪 + DEBUG 日志")
    ] = False,  # noqa: E501
    json_output: Annotated[bool, typer.Option("--json", help="JSON 格式输出")] = False,
) -> None:
    """Show flow details."""
    if trace:
        setup_logging(verbose=2)

    ctx = trace_context(command="flow show", domain="flow") if trace else _noop()
    with ctx:
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
    if trace:
        setup_logging(verbose=2)

    ctx = trace_context(command="flow status", domain="flow") if trace else _noop()
    with ctx:
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
    if trace:
        setup_logging(verbose=2)

    ctx = trace_context(command="flow list", domain="flow") if trace else _noop()
    with ctx:
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
