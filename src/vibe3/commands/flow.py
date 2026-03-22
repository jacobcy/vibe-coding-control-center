#!/usr/bin/env python3
"""Flow command handlers."""

import json
from contextlib import contextmanager
from typing import TYPE_CHECKING, Annotated, Iterator, Literal

import typer
from loguru import logger

from vibe3.clients.git_client import GitClient
from vibe3.observability.logger import setup_logging
from vibe3.observability.trace import trace_context
from vibe3.services.flow_service import FlowService
from vibe3.ui.flow_ui import (
    render_error,
    render_flow_created,
    render_flow_status,
    render_flows_status_dashboard,
    render_flows_table,
)

if TYPE_CHECKING:
    from vibe3.clients.github_client import GitHubClient
    from vibe3.models.flow import FlowStatusResponse

app = typer.Typer(
    help="Manage logic flows (branch-centric)",
    no_args_is_help=True,
    rich_markup_mode="rich",
)


@contextmanager
def _noop() -> Iterator[None]:
    yield


def _fetch_issue_titles(
    gh: "GitHubClient", flow_status: "FlowStatusResponse"
) -> tuple[dict[int, str], "dict[str, object] | None", bool]:
    """拉取 flow 关联 issue title 和 PR 信息。network_error=True 表示网络故障。"""
    titles: dict[int, str] = {}
    network_error = False
    numbers: set[int] = set()
    if flow_status.task_issue_number:
        numbers.add(flow_status.task_issue_number)
    for link in flow_status.issues:
        numbers.add(link.issue_number)

    for n in numbers:
        result = gh.view_issue(n)
        if result == "network_error":
            network_error = True
            break
        if isinstance(result, dict):
            titles[n] = result.get("title", "")

    pr_data: dict[str, object] | None = None
    if flow_status.pr_number and not network_error:
        try:
            pr = gh.get_pr(flow_status.pr_number)
            if pr:
                pr_data = {
                    "number": pr.number,
                    "title": pr.title,
                    "state": pr.state.value,
                    "draft": pr.draft,
                    "url": pr.url,
                }
        except Exception:
            network_error = True

    return titles, pr_data, network_error


@app.command()
def new(
    name: Annotated[str, typer.Argument(help="Flow name")],
    task_issue: Annotated[
        int | None, typer.Option("--task-issue", help="Task issue number to bind")
    ] = None,
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
        logger.bind(
            command="flow new", name=name, task_issue=task_issue, actor=actor
        ).info("Creating new flow")

        git = GitClient()
        branch = git.get_current_branch()
        service = FlowService()
        flow = service.create_flow(slug=name, branch=branch, actor=actor)

        if task_issue is not None:
            from vibe3.services.task_service import TaskService

            TaskService().link_issue(branch, task_issue, role="task", actor=actor)
            flow.task_issue_number = task_issue

        if json_output:
            typer.echo(json.dumps(flow.model_dump(), indent=2, default=str))
        else:
            render_flow_created(flow, str(task_issue) if task_issue else None)


@app.command()
def bind(
    task_id: Annotated[str, typer.Argument(help="Task issue number or URL")],
    actor: Annotated[str, typer.Option(help="Actor binding the task")] = "claude",
    trace: Annotated[
        bool, typer.Option("--trace", help="启用调用链路追踪 + DEBUG 日志")
    ] = False,
    json_output: Annotated[bool, typer.Option("--json", help="JSON 格式输出")] = False,
) -> None:
    """Bind a task issue to current flow (flow perspective of task link)."""
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

        from vibe3.commands.task import parse_issue_url
        from vibe3.services.task_service import TaskService

        git = GitClient()
        branch = git.get_current_branch()

        try:
            issue_number = parse_issue_url(task_id)
        except ValueError:
            import re

            match = re.search(r"\d+", task_id)
            if not match:
                typer.echo(f"Error: 无法解析 task ID: {task_id}", err=True)
                raise typer.Exit(1)
            issue_number = int(match.group())

        task_service = TaskService()
        issue_link = task_service.link_issue(
            branch, issue_number, role="task", actor=actor
        )

        if json_output:
            typer.echo(json.dumps(issue_link.model_dump(), indent=2, default=str))
        else:
            from vibe3.ui.task_ui import render_issue_linked

            render_issue_linked(issue_link)


@app.command()
def show(
    flow_name: Annotated[str | None, typer.Argument(help="Flow to show")] = None,
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
        git = GitClient()
        service = FlowService()
        branch = flow_name if flow_name else git.get_current_branch()
        flow_status = service.get_flow_status(branch)

        if not flow_status:
            logger.error(f"Flow not found: {branch}")
            raise typer.Exit(1)

        if json_output:
            typer.echo(json.dumps(flow_status.model_dump(), indent=2, default=str))
        else:
            from vibe3.clients.github_client import GitHubClient

            gh = GitHubClient()
            issue_titles, pr_data, net_err = _fetch_issue_titles(gh, flow_status)
            if net_err:
                render_error("网络故障，远端 issue/PR 信息不可用（本地数据仍显示）")
            render_flow_status(flow_status, issue_titles, pr_data)


@app.command()
def status(
    json_output: Annotated[bool, typer.Option("--json", help="JSON output")] = False,
    trace: Annotated[
        bool, typer.Option("--trace", help="启用调用链路追踪 + DEBUG 日志")
    ] = False,
) -> None:
    """Show dashboard of all active flows with remote task titles (大盘概况)."""
    if trace:
        setup_logging(verbose=2)

    ctx = trace_context(command="flow status", domain="flow") if trace else _noop()
    with ctx:
        logger.bind(command="flow status", json_output=json_output).info(
            "Getting active flows dashboard"
        )

        service = FlowService()
        flows = service.list_flows(status="active")

        if json_output:
            typer.echo(
                json.dumps([f.model_dump() for f in flows], indent=2, default=str)
            )
            return

        if not flows:
            typer.echo("No active flows")
            raise typer.Exit(0)

        from vibe3.clients.github_client import GitHubClient

        gh = GitHubClient()
        titles: dict[int, str] = {}
        net_err = False
        for flow in flows:
            if flow.task_issue_number and flow.task_issue_number not in titles:
                r = gh.view_issue(flow.task_issue_number)
                if r == "network_error":
                    net_err = True
                    break
                if isinstance(r, dict):
                    titles[flow.task_issue_number] = r.get("title", "")
        if net_err:
            render_error("网络故障，远端 issue title 不可用（本地数据仍显示）")
        render_flows_status_dashboard(flows, titles)


@app.command()
def list(
    all_flows: Annotated[
        bool, typer.Option("--all", help="显示所有 flow（含历史）")
    ] = False,
    status_filter: Annotated[
        Literal["active", "blocked", "done", "stale"] | None,
        typer.Option("--status", help="按状态过滤"),
    ] = None,
    trace: Annotated[
        bool, typer.Option("--trace", help="启用调用链路追踪 + DEBUG 日志")
    ] = False,
    json_output: Annotated[bool, typer.Option("--json", help="JSON 格式输出")] = False,
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

        if all_flows:
            flows = service.list_flows(status=status_filter)
        else:
            # 默认只显示 active
            flows = service.list_flows(status=status_filter or "active")

        if not flows:
            logger.info("No flows found")
            raise typer.Exit(0)

        if json_output:
            typer.echo(
                json.dumps([f.model_dump() for f in flows], indent=2, default=str)
            )
        else:
            render_flows_table(flows)
