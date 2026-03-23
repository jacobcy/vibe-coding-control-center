#!/usr/bin/env python3
"""Flow command handlers."""

import json
from contextlib import contextmanager
from typing import Annotated, Iterator, Literal

import typer
from loguru import logger

from vibe3.clients.git_client import GitClient
from vibe3.commands.flow_lifecycle import (
    aborted as _aborted,
)
from vibe3.commands.flow_lifecycle import (
    blocked as _blocked,
)
from vibe3.commands.flow_lifecycle import (
    done as _done,
)
from vibe3.commands.flow_lifecycle import (
    switch as _switch,
)
from vibe3.commands.flow_status import show as _show
from vibe3.commands.flow_status import status as _status
from vibe3.commands.task import parse_issue_ref
from vibe3.observability.logger import setup_logging
from vibe3.observability.trace import trace_context
from vibe3.services.flow_service import FlowService
from vibe3.services.task_service import TaskService
from vibe3.ui.flow_ui import render_flow_created, render_flows_table
from vibe3.ui.task_ui import render_issue_linked

app = typer.Typer(
    help="Manage logic flows (branch-centric)",
    no_args_is_help=True,
    rich_markup_mode="rich",
)


@contextmanager
def _noop() -> Iterator[None]:
    yield


def _default_flow_name(branch: str) -> str:
    return branch.split("/", 1)[1] if "/" in branch else branch


@app.command()
def new(
    name: Annotated[
        str | None,
        typer.Argument(help="Flow name (default: branch name without prefix)"),
    ] = None,
    issue: Annotated[
        str | None,
        typer.Option("--issue", help="Issue number (or URL) to bind as task"),
    ] = None,
    trace: Annotated[bool, typer.Option("--trace")] = False,
    json_output: Annotated[bool, typer.Option("--json")] = False,
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
        logger.bind(command="flow new", name=name, issue=issue).info(
            "Creating new flow"
        )
        git = GitClient()
        branch = git.get_current_branch()
        slug = name or _default_flow_name(branch)
        service = FlowService()
        flow = service.create_flow(slug=slug, branch=branch)
        if issue is not None:
            issue_number = parse_issue_ref(issue)
            TaskService().link_issue(branch, issue_number, role="task")
            flow.task_issue_number = issue_number
        if json_output:
            typer.echo(json.dumps(flow.model_dump(), indent=2, default=str))
        else:
            render_flow_created(flow, str(flow.task_issue_number) if issue else None)


@app.command()
def bind(
    issue: Annotated[str, typer.Argument(help="Issue number (or URL)")],
    role: Annotated[
        Literal["task", "related", "dependency"],
        typer.Option(help="Issue role in flow"),
    ] = "task",
    trace: Annotated[bool, typer.Option("--trace")] = False,
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Bind a task issue to current flow."""
    if trace:
        setup_logging(verbose=2)
    ctx = (
        trace_context(command="flow bind", domain="flow", issue=issue, role=role)
        if trace
        else _noop()
    )
    with ctx:
        logger.bind(command="flow bind", issue=issue, role=role).info(
            "Binding task to flow"
        )
        git = GitClient()
        branch = git.get_current_branch()
        try:
            issue_number = parse_issue_ref(issue)
        except ValueError as exc:
            typer.echo(f"Error: {exc}", err=True)
            raise typer.Exit(1)
        task_service = TaskService()
        issue_link = task_service.link_issue(branch, issue_number, role=role)
        if json_output:
            typer.echo(json.dumps(issue_link.model_dump(), indent=2, default=str))
        else:
            render_issue_linked(issue_link)


@app.command()
def list(
    all_flows: Annotated[
        bool, typer.Option("--all", help="显示所有 flow（含历史）")
    ] = False,
    status_filter: Annotated[
        Literal["active", "blocked", "done", "stale"] | None, typer.Option("--status")
    ] = None,
    trace: Annotated[bool, typer.Option("--trace")] = False,
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """List flows. Default: active only. Use --all to include history."""
    if trace:
        setup_logging(verbose=2)
    ctx = trace_context(command="flow list", domain="flow") if trace else _noop()
    with ctx:
        logger.bind(
            command="flow list", all_flows=all_flows, status_filter=status_filter
        ).info("Listing flows")
        service = FlowService()
        flows = (
            service.list_flows(status=status_filter)
            if all_flows
            else service.list_flows(status=status_filter or "active")
        )
        if not flows:
            logger.info("No flows found")
            raise typer.Exit(0)
        if json_output:
            typer.echo(
                json.dumps([f.model_dump() for f in flows], indent=2, default=str)
            )
        else:
            render_flows_table(flows)


@app.command()
def show(
    branch: Annotated[str | None, typer.Argument(help="Branch name")] = None,
    trace: Annotated[bool, typer.Option("--trace")] = False,
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Show flow details."""
    _show(branch=branch, trace=trace, json_output=json_output)


@app.command()
def status(
    json_output: Annotated[bool, typer.Option("--json")] = False,
    trace: Annotated[bool, typer.Option("--trace")] = False,
) -> None:
    """Show dashboard of all active flows."""
    _status(json_output=json_output, trace=trace)


@app.command()
def switch(
    target: Annotated[str, typer.Argument(help="Flow slug or branch name")],
    trace: Annotated[bool, typer.Option("--trace")] = False,
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Switch to existing flow."""
    _switch(target, trace=trace, json_output=json_output)


@app.command()
def done(
    branch: Annotated[str | None, typer.Option("--branch")] = None,
    yes: Annotated[bool, typer.Option("--yes", "-y")] = False,
    trace: Annotated[bool, typer.Option("--trace")] = False,
) -> None:
    """Close flow and delete branch."""
    _done(branch=branch, yes=yes, trace=trace)


@app.command()
def blocked(
    branch: Annotated[str | None, typer.Option("--branch")] = None,
    reason: Annotated[str | None, typer.Option("--reason")] = None,
    by: Annotated[int | None, typer.Option("--by")] = None,
    trace: Annotated[bool, typer.Option("--trace")] = False,
) -> None:
    """Mark flow as blocked. Use --by to link dependency issue."""
    _blocked(branch=branch, reason=reason, by=by, trace=trace)


@app.command()
def aborted(
    branch: Annotated[str | None, typer.Option("--branch")] = None,
    trace: Annotated[bool, typer.Option("--trace")] = False,
) -> None:
    """Abort flow and delete branch."""
    _aborted(branch=branch, trace=trace)
