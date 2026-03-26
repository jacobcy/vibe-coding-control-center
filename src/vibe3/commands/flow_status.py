"""Flow status commands - show, status."""

import json
from typing import TYPE_CHECKING, Annotated

import typer
from loguru import logger

from vibe3.commands.common import trace_scope
from vibe3.services.flow_service import FlowService
from vibe3.ui.flow_ui import (
    render_error,
    render_flow_status,
    render_flow_timeline,
    render_flows_status_dashboard,
)

if TYPE_CHECKING:
    from vibe3.clients.github_client import GitHubClient
    from vibe3.models.flow import FlowStatusResponse


def _fetch_issue_titles(
    gh: "GitHubClient", flow_status: "FlowStatusResponse"
) -> tuple[dict[int, str], "dict[str, object] | None", bool]:
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


def show(
    branch: Annotated[str | None, typer.Argument(help="Branch name")] = None,
    snapshot: Annotated[bool, typer.Option("--snapshot", help="静态快照模式")] = False,
    trace: Annotated[bool, typer.Option("--trace")] = False,
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Show flow details."""
    with trace_scope(trace, "flow show", domain="flow"):
        service = FlowService()
        target_branch = branch if branch else service.get_current_branch()

    if snapshot:
        flow_status = service.get_flow_status(target_branch)
        if not flow_status:
            logger.error(f"Flow not found: {target_branch}")
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
        return

    timeline = service.get_flow_timeline(target_branch)
    if not timeline["state"]:
        logger.error(f"Flow not found: {target_branch}")
        raise typer.Exit(1)

    if json_output:
        output = {
            "state": timeline["state"].model_dump(),
            "events": [e.model_dump() for e in timeline["events"]],
        }
        typer.echo(json.dumps(output, indent=2, default=str))
    else:
        render_flow_timeline(timeline["state"], timeline["events"])


def status(
    json_output: Annotated[bool, typer.Option("--json")] = False,
    trace: Annotated[bool, typer.Option("--trace")] = False,
) -> None:
    """Show dashboard of all active flows."""
    with trace_scope(trace, "flow status", domain="flow"):
        service = FlowService()
        flows = service.list_flows(status="active")
    if json_output:
        typer.echo(json.dumps([f.model_dump() for f in flows], indent=2, default=str))
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
