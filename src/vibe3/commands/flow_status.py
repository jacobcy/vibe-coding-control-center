"""Flow status commands - show, status."""

import json
from typing import TYPE_CHECKING, Annotated

import typer
from loguru import logger

from vibe3.commands.command_options import ensure_flow_for_current_branch
from vibe3.commands.common import trace_scope
from vibe3.services.flow_projection_service import FlowProjectionService
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
    pass


StatusOption = Annotated[bool, typer.Option("--snapshot", help="静态快照模式")]
AllOption = Annotated[
    bool, typer.Option("--all", help="显示所有状态的 flow（含 done/aborted/stale）")
]
JsonOption = Annotated[bool, typer.Option("--json")]
TraceOption = Annotated[bool, typer.Option("--trace")]


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
            projection_service = FlowProjectionService()
            projection = projection_service.get_projection(target_branch)

            if json_output:
                # Convert projection to dict for JSON output
                output = {
                    "branch": projection.branch,
                    "flow_slug": projection.flow_slug,
                    "flow_status": projection.flow_status,
                    "task_issue_number": projection.task_issue_number,
                    "pr_number": projection.pr_number,
                    "pr_ready_for_review": projection.pr_ready_for_review,
                    "spec_ref": projection.spec_ref,
                    "plan_ref": projection.plan_ref,
                    "report_ref": projection.report_ref,
                    "audit_ref": projection.audit_ref,
                    "planner_actor": projection.planner_actor,
                    "planner_session_id": projection.planner_session_id,
                    "executor_actor": projection.executor_actor,
                    "executor_session_id": projection.executor_session_id,
                    "reviewer_actor": projection.reviewer_actor,
                    "reviewer_session_id": projection.reviewer_session_id,
                    "latest_actor": projection.latest_actor,
                    "blocked_by": projection.blocked_by,
                    "next_step": projection.next_step,
                    "planner_status": projection.planner_status,
                    "executor_status": projection.executor_status,
                    "reviewer_status": projection.reviewer_status,
                    "execution_pid": projection.execution_pid,
                    "execution_started_at": projection.execution_started_at,
                    "execution_completed_at": projection.execution_completed_at,
                    "project_item_id": projection.project_item_id,
                    "title": projection.title,
                    "body": projection.body,
                    "status": projection.status,
                    "priority": projection.priority,
                    "assignees": projection.assignees,
                    "offline_mode": projection.offline_mode,
                    "identity_drift": projection.identity_drift,
                    "pr_title": projection.pr_title,
                    "pr_state": projection.pr_state,
                    "pr_draft": projection.pr_draft,
                    "pr_url": projection.pr_url,
                }
                typer.echo(json.dumps(output, indent=2, default=str))
            else:
                flow_status = service.get_flow_status(target_branch)
                if not flow_status:
                    logger.error(f"Flow not found: {target_branch}")
                    raise typer.Exit(1)

                # Fetch issue titles and milestone data using projection service
                issue_numbers = set()
                if flow_status.task_issue_number:
                    issue_numbers.add(flow_status.task_issue_number)
                for link in flow_status.issues:
                    issue_numbers.add(link.issue_number)

                issue_titles, network_error = projection_service.get_issue_titles(
                    list(issue_numbers)
                )
                milestone_data = None
                if flow_status.task_issue_number and not network_error:
                    milestone_data = projection_service.get_milestone_data(
                        flow_status.task_issue_number
                    )

                # Build PR data from projection
                pr_data = None
                if projection.pr_number and not projection.pr_fetch_error:
                    pr_data = {
                        "number": projection.pr_number,
                        "title": projection.pr_title,
                        "state": projection.pr_state,
                        "draft": projection.pr_draft,
                        "url": projection.pr_url,
                    }

                if (
                    network_error
                    or projection.hydrate_error
                    or projection.pr_fetch_error
                ):
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
                projection_service = FlowProjectionService()
                milestone_data = projection_service.get_milestone_data(task_issue)
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

        # Use projection service to fetch issue titles
        projection_service = FlowProjectionService()
        issue_numbers = set()
        for flow in flows:
            if flow.task_issue_number:
                issue_numbers.add(flow.task_issue_number)

        titles, net_err = projection_service.get_issue_titles(list(issue_numbers))

        # Build PR and worktree maps via projection service
        pr_map: dict[str, dict[str, object]] = {}
        worktree_map: dict[str, str] = {}
        try:
            from vibe3.clients.git_client import GitClient

            git = GitClient()
            worktree_output = git._run(["worktree", "list", "--porcelain"])
            current_worktree = ""
            for line in worktree_output.splitlines():
                line = line.strip()
                if line.startswith("worktree "):
                    current_worktree = line.split(" ", 1)[1]
                elif line.startswith("branch ") and current_worktree:
                    branch_ref = line.split(" ", 1)[1]
                    branch = branch_ref.removeprefix("refs/heads/")
                    worktree_name = current_worktree.split("/")[-1]
                    worktree_map[branch] = worktree_name
        except Exception:
            pass

        for flow in flows:
            try:
                pr = projection_service.pr_service.get_pr(branch=flow.branch)
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
