"""Flow information commands (show, status, list)."""

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
    render_flow_status,
    render_flows_status_dashboard,
    render_flows_table,
)


def show(
    branch: Annotated[str | None, typer.Argument(help="Branch name")] = None,
    trace: Annotated[
        bool, typer.Option("--trace", help="启用调用链路追踪 + DEBUG 日志")
    ] = False,
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
