"""Flow status commands - show, status."""

import json
from typing import TYPE_CHECKING, Annotated

import typer
from loguru import logger

from vibe3.commands.command_options import ensure_flow_for_current_branch
from vibe3.commands.common import trace_scope
from vibe3.services.flow_service import FlowService
from vibe3.services.task_binding_guard import build_bind_task_hint
from vibe3.ui.console import console
from vibe3.ui.flow_ui import (
    render_error,
    render_flow_status,
    render_flow_timeline,
    render_flows_status_dashboard,
)

if TYPE_CHECKING:
    from vibe3.clients.github_client import GitHubClient
    from vibe3.models.flow import FlowStatusResponse


StatusOption = Annotated[bool, typer.Option("--snapshot", help="静态快照模式")]
AllOption = Annotated[
    bool, typer.Option("--all", help="显示所有状态的 flow（含 done/aborted/stale）")
]
JsonOption = Annotated[bool, typer.Option("--json")]
TraceOption = Annotated[bool, typer.Option("--trace")]


def _fetch_issue_titles(
    gh: "GitHubClient", flow_status: "FlowStatusResponse"
) -> "tuple[dict[int, str], dict[str, object] | None, bool, dict[str, object] | None]":
    titles: dict[int, str] = {}
    network_error = False
    milestone_data: dict[str, object] | None = None
    numbers: set[int] = set()
    if flow_status.task_issue_number:
        numbers.add(flow_status.task_issue_number)
    for link in flow_status.issues:
        numbers.add(link.issue_number)
    for n in numbers:
        try:
            result = gh.view_issue(n)
        except Exception as e:
            logger.debug(f"Skipping flow: {e}")
            continue
        if result == "network_error":
            network_error = True
            break
        if isinstance(result, dict):
            titles[n] = result.get("title", "")
            if n == flow_status.task_issue_number and result.get("milestone"):
                ms = result["milestone"]
                ms_issues = gh.get_milestone_issues(ms["number"])
                open_count = sum(
                    1 for i in ms_issues if str(i.get("state", "")).upper() == "OPEN"
                )
                closed_count = sum(
                    1 for i in ms_issues if str(i.get("state", "")).upper() == "CLOSED"
                )
                milestone_data = {
                    "number": ms["number"],
                    "title": ms["title"],
                    "open": open_count,
                    "closed": closed_count,
                    "issues": ms_issues,
                    "task_issue": n,
                }
    pr_data: dict[str, object] | None = None
    if not network_error:
        try:
            pr = None
            if flow_status.pr_number:
                pr = gh.get_pr(flow_status.pr_number)
            if not pr:
                # Remote-first fallback: cached PR id may miss or drift.
                pr = gh.get_pr(branch=flow_status.branch)
            if pr:
                pr_data = {
                    "number": pr.number,
                    "title": pr.title,
                    "state": pr.state.value,
                    "draft": pr.draft,
                    "url": pr.url,
                }
        except Exception as e:
            logger.debug(f"Skipping flow: {e}")
            network_error = True
    return titles, pr_data, network_error, milestone_data


def show(
    branch: Annotated[
        str | None,
        typer.Option("--branch", "-b", help="Branch name (defaults to current branch)"),
    ] = None,
    snapshot: StatusOption = False,
    trace: TraceOption = False,
    json_output: JsonOption = False,
) -> None:
    """Show flow details."""
    with trace_scope(trace, "flow show", domain="flow"):
        if branch:
            service = FlowService()
            target_branch = branch
        else:
            service, target_branch = ensure_flow_for_current_branch()

        if snapshot:
            flow_status = service.get_flow_status(target_branch)
            if not flow_status:
                logger.error(f"Flow not found: {target_branch}")
                raise typer.Exit(1)
            if json_output:
                typer.echo(json.dumps(flow_status.model_dump(), indent=2, default=str))
            else:
                # TODO: move GitHubClient calls to a service method in a follow-up PR
                from vibe3.clients.github_client import GitHubClient

                gh = GitHubClient()
                issue_titles, pr_data, net_err, milestone_data = _fetch_issue_titles(
                    gh, flow_status
                )
                if net_err:
                    render_error("网络故障，远端 issue/PR 信息不可用（本地数据仍显示）")
                render_flow_status(flow_status, issue_titles, pr_data, milestone_data)
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
            milestone_data = None
            task_issue = timeline["state"].task_issue_number
            if task_issue:
                from vibe3.clients.github_client import GitHubClient

                gh = GitHubClient()
                issue = gh.view_issue(task_issue)
                if isinstance(issue, dict) and issue.get("milestone"):
                    ms = issue["milestone"]
                    ms_issues = gh.get_milestone_issues(ms["number"])
                    open_count = sum(
                        1
                        for i in ms_issues
                        if str(i.get("state", "")).upper() == "OPEN"
                    )
                    closed_count = sum(
                        1
                        for i in ms_issues
                        if str(i.get("state", "")).upper() == "CLOSED"
                    )
                    milestone_data = {
                        "number": ms["number"],
                        "title": ms["title"],
                        "open": open_count,
                        "closed": closed_count,
                        "issues": ms_issues,
                        "task_issue": task_issue,
                    }
            render_flow_timeline(timeline["state"], timeline["events"], milestone_data)
            if timeline["state"].task_issue_number is None:
                console.print(
                    "[yellow]提示：当前 flow 还没有 task，建议 "
                    f"{build_bind_task_hint()}[/]"
                )


def status(
    all_flows: AllOption = False,
    json_output: JsonOption = False,
    trace: TraceOption = False,
) -> None:
    """Show dashboard of all active flows.

    By default only shows active flows. Use --all to include done/aborted/stale.
    """
    with trace_scope(trace, "flow status", domain="flow"):
        service = FlowService()
        flows = service.list_flows(status=None if all_flows else "active")
        if json_output:
            typer.echo(
                json.dumps([f.model_dump() for f in flows], indent=2, default=str)
            )
            return
        if not flows:
            typer.echo("No active flows")
            raise typer.Exit(0)
        # TODO: move GitHubClient calls to a service method in a follow-up PR
        from vibe3.clients.git_client import GitClient
        from vibe3.clients.github_client import GitHubClient

        gh = GitHubClient()
        git = GitClient()
        titles: dict[int, str] = {}
        pr_map: dict[str, dict[str, object]] = {}
        worktree_map: dict[str, str] = {}
        net_err = False

        # Get worktree to branch mapping
        try:
            worktree_output = git._run(["worktree", "list", "--porcelain"])
            current_worktree = ""
            for line in worktree_output.splitlines():
                line = line.strip()
                if line.startswith("worktree "):
                    current_worktree = line.split(" ", 1)[1]
                elif line.startswith("branch ") and current_worktree:
                    branch_ref = line.split(" ", 1)[1]
                    branch = branch_ref.removeprefix(
                        "refs/heads/"
                    )  # Get full branch name
                    # Store only worktree basename for concise display
                    worktree_name = current_worktree.split("/")[-1]
                    worktree_map[branch] = worktree_name
        except Exception:
            pass
        for flow in flows:
            if flow.task_issue_number and flow.task_issue_number not in titles:
                r = gh.view_issue(flow.task_issue_number)
                if r == "network_error":
                    net_err = True
                    break
                if isinstance(r, dict):
                    titles[flow.task_issue_number] = r.get("title", "")
            # Fetch PR data for each flow (remote-first fallback)
            try:
                pr = None
                if flow.pr_number:
                    pr = gh.get_pr(flow.pr_number)
                if not pr:
                    pr = gh.get_pr(branch=flow.branch)
                if pr:
                    pr_map[flow.branch] = {
                        "number": pr.number,
                        "title": pr.title,
                        "state": pr.state.value,
                        "draft": pr.draft,
                        "url": pr.url,
                        "worktree": worktree_map.get(flow.branch),
                    }
            except Exception:
                pass
        if net_err:
            render_error("网络故障，远端 issue title 不可用（本地数据仍显示）")
        render_flows_status_dashboard(flows, titles, pr_map, worktree_map)
