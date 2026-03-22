#!/usr/bin/env python3
"""Flow command handlers."""

import json
from typing import Annotated, Literal

import typer
from loguru import logger

from vibe3.clients.git_client import GitClient
from vibe3.commands.flow_helpers import _noop, fetch_issue_titles
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

app = typer.Typer(
    help="Manage logic flows (branch-centric)",
    no_args_is_help=True,
    rich_markup_mode="rich",
)


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
        logger.bind(command="flow new", name=name, issue=issue, actor=actor).info(
            "Creating new flow"
        )

        git = GitClient()
        branch = git.get_current_branch()
        slug = name if name else branch.split("/")[-1]
        service = FlowService()
        flow = service.create_flow(slug=slug, branch=branch, actor=actor)

        if issue is not None:
            from vibe3.commands.task import parse_issue_ref
            from vibe3.services.task_service import TaskService

            issue_number = parse_issue_ref(issue)
            TaskService().link_issue(branch, issue_number, role="task", actor=actor)
            flow.task_issue_number = issue_number

        if json_output:
            typer.echo(json.dumps(flow.model_dump(), indent=2, default=str))
        else:
            render_flow_created(flow, issue)


@app.command()
def bind(
    issue: Annotated[str, typer.Argument(help="Issue number (or URL)")],
    role: Annotated[
        Literal["task", "related", "dependency"],
        typer.Option(help="Issue role in flow"),
    ] = "task",
    branch: Annotated[
        str | None,
        typer.Option("--branch", help="Branch name (default: current branch)"),
    ] = None,
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
        trace_context(command="flow bind", domain="flow", issue=issue, role=role)
        if trace
        else _noop()
    )
    with ctx:
        logger.bind(command="flow bind", issue=issue, role=role, actor=actor).info(
            "Binding issue to flow"
        )

        from vibe3.commands.task import parse_issue_ref
        from vibe3.services.task_service import TaskService

        git = GitClient()
        target_branch = branch if branch else git.get_current_branch()

        try:
            issue_number = parse_issue_ref(issue)
        except ValueError:
            import re

            match = re.search(r"\d+", issue)
            if not match:
                typer.echo(f"Error: 无法解析 issue: {issue}", err=True)
                raise typer.Exit(1)
            issue_number = int(match.group())

        task_service = TaskService()
        issue_link = task_service.link_issue(
            target_branch, issue_number, role=role, actor=actor
        )

        if json_output:
            typer.echo(json.dumps(issue_link.model_dump(), indent=2, default=str))
        else:
            from vibe3.ui.task_ui import render_issue_linked

            render_issue_linked(issue_link)


@app.command()
def show(
    branch: Annotated[str | None, typer.Argument(help="Branch name")] = None,
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
        target_branch = branch if branch else git.get_current_branch()
        flow_status = service.get_flow_status(target_branch)

        if not flow_status:
            logger.error(f"Flow not found: {target_branch}")
            raise typer.Exit(1)

        if json_output:
            typer.echo(json.dumps(flow_status.model_dump(), indent=2, default=str))
        else:
            from vibe3.clients.github_client import GitHubClient

            gh = GitHubClient()
            issue_titles, pr_data, net_err = fetch_issue_titles(gh, flow_status)
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
        prs_data: dict[str, dict[str, object]] = {}
        net_err = False
        for flow in flows:
            if flow.task_issue_number and flow.task_issue_number not in titles:
                r = gh.view_issue(flow.task_issue_number)
                if r == "network_error":
                    net_err = True
                    break
                if isinstance(r, dict):
                    titles[flow.task_issue_number] = r.get("title", "")
            # Fetch PR data if flow has PR number
            if flow.pr_number and flow.branch not in prs_data and not net_err:
                try:
                    pr = gh.get_pr(flow.pr_number)
                    if pr:
                        prs_data[flow.branch] = {
                            "number": pr.number,
                            "title": pr.title,
                            "state": pr.state.value,
                            "draft": pr.draft,
                            "url": pr.url,
                        }
                except Exception:
                    net_err = True
        if net_err:
            render_error("网络故障，远端 issue/PR 信息不可用（本地数据仍显示）")
        render_flows_status_dashboard(flows, titles, prs_data)


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
