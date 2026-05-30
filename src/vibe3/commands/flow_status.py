"""Flow status commands - show, status."""

import json
from typing import Annotated

import typer
from loguru import logger

from vibe3.commands.command_options import (
    ActorFilterOption,
    AllOption,
    FormatOption,
    RemoteOption,
    TraceMinMsOption,
    TraceOption,
)
from vibe3.commands.common import (
    enable_method_trace,
    run_full_check_shortcut,
    validate_trace_options,
)
from vibe3.commands.flow_status_helpers import (
    _collect_timeline_issue_numbers,
    _fetch_issue_titles_for_status,
    _fetch_pr_map,
    _fetch_worktree_map,
    _get_yaml,
    _parse_remote_issue_number,
    _render_snapshot_format,
    _timeline_to_flow_events,
)
from vibe3.config.orchestra_settings import load_orchestra_config
from vibe3.exceptions import SystemError, UserError
from vibe3.services import (
    FlowProjectionService,
    FlowService,
    PRService,
    build_bind_task_hint,
    resolve_command_branch,
)
from vibe3.ui.console import console
from vibe3.ui.flow_ui import (
    render_error,
    render_flow_timeline,
    render_flows_status_dashboard,
)
from vibe3.utils.branch_utils import find_parent_branch

StatusOption = Annotated[bool, typer.Option("--snapshot", help="静态快照模式")]


def show(
    branch_arg: Annotated[
        str | None,
        typer.Argument(help="Branch name"),
    ] = None,
    branch_opt: Annotated[
        str | None, typer.Option("--branch", help="Branch name or issue number")
    ] = None,
    pr_opt: Annotated[
        int | None,
        typer.Option("--pr", help="PR number to resolve branch from"),
    ] = None,
    snapshot: StatusOption = False,
    trace: TraceOption = False,
    min_ms: TraceMinMsOption = None,
    output_format: FormatOption = "table",
    remote: RemoteOption = False,
    show_all: Annotated[
        bool, typer.Option("--show-all", help="Show orchestra actor events")
    ] = False,
    actor_filter: ActorFilterOption = None,
    json_output: Annotated[
        bool,
        typer.Option(
            "--json",
            help="[DEPRECATED] Use --format json instead",
            hidden=True,
        ),
    ] = False,
) -> None:
    """Show flow details with source-aware reads."""
    validate_trace_options(trace, min_ms)
    if trace:
        enable_method_trace(min_ms=min_ms)

    # Handle deprecated --json flag
    if json_output and output_format == "table":
        typer.echo(
            "Warning: --json is deprecated, use --format json instead",
            err=True,
        )
        output_format = "json"

    service = FlowService()

    # Handle --remote mode: parse issue number directly, bypass local resolution
    task_issue_number: int | None
    if remote:
        raw = branch_opt or branch_arg
        if raw is None:
            raise UserError(
                "Cannot use --remote without an issue number. "
                "Provide it as: flow show --remote <issue_number>"
            )
        task_issue_number = _parse_remote_issue_number(raw)
        target_branch = f"remote-#{task_issue_number}"
    else:
        # Local mode: resolve branch via standard resolution
        try:
            target_branch = resolve_command_branch(
                branch_opt=branch_opt,
                pr_opt=pr_opt,
                position_arg=branch_arg,
                flow_service=service,
            )
        except (UserError, SystemError) as error:
            typer.echo(f"Error: {error}", err=True)
            raise typer.Exit(1) from error

        # Get task issue number for remote fallback
        links = service.store.get_issue_links(target_branch)
        task_issue_number = next(
            (link["issue_number"] for link in links if link["issue_role"] == "task"),
            None,
        )

        # Fallback: parse issue number from branch name when local DB missing
        if task_issue_number is None:
            from vibe3.services import IssueFlowService

            issue_flow_service = IssueFlowService(store=service.store)
            task_issue_number = issue_flow_service.parse_issue_number_any(target_branch)

    # Use resolver for source-aware read
    from vibe3.services import FlowStatusResolver

    resolver = FlowStatusResolver(store=service.store, flow_service=service)
    flow_status = resolver.resolve(
        branch=target_branch,
        remote=remote,
        issue_number=task_issue_number,
    )

    # Handle non-registered flow or special branches
    if not flow_status or flow_status.flow_status == "aborted":
        if output_format == "table":
            from vibe3.services import FlowService as FlowService_

            is_safe = target_branch.startswith(FlowService_.SAFE_BRANCH_PREFIX)
            is_aborted = flow_status and flow_status.flow_status == "aborted"

            if is_safe:
                console.print(
                    f"[yellow]提示：当前分支 '{target_branch}' 为安全分支（只读），"
                    "不建议在此开发。[/]"
                )
                console.print(
                    "[yellow]建议切换到新分支：`git checkout -b <new-branch>`[/]"
                )
            elif is_aborted:
                console.print(
                    f"[red]警告：当前分支 '{target_branch}' 的 flow 已被标记为 "
                    "aborted（已废弃）。[/]"
                )
                console.print("[yellow]不建议继续在此开发，建议创建新分支。[/]")
            else:
                console.print(
                    f"[yellow]提示：当前分支 '{target_branch}' 尚未注册为 flow。[/]"
                )
                console.print(
                    "[cyan]运行 `vibe3 flow update` 即可追踪此分支的开发进度。[/]"
                )

            raise typer.Exit(0)
        else:
            if not flow_status:
                output_data = {
                    "error": "Flow not registered",
                    "branch": target_branch,
                }
                if output_format == "json":
                    typer.echo(json.dumps(output_data))
                else:
                    typer.echo(
                        _get_yaml().dump(
                            output_data,
                            default_flow_style=False,
                            allow_unicode=True,
                        )
                    )
                raise typer.Exit(1)
            elif flow_status and flow_status.flow_status == "aborted":
                # Handle aborted flow with json/yaml output
                output_data = {
                    "error": "Flow aborted",
                    "branch": target_branch,
                }
                if output_format == "json":
                    typer.echo(json.dumps(output_data))
                else:
                    typer.echo(
                        _get_yaml().dump(
                            output_data,
                            default_flow_style=False,
                            allow_unicode=True,
                        )
                    )
                raise typer.Exit(1)

    if snapshot:
        # Use resolver's flow_status directly (already source-aware)
        # Do NOT re-read from local via FlowProjectionService.get_projection
        from vibe3.services import FlowProjection

        projection = FlowProjection.from_flow_status(flow_status)

        # Fetch real-time PR status by branch (regardless of flow_status.pr_number)
        # For --remote, flow_status may not have pr_number from issue-body
        # but branch could still have an open PR
        try:
            pr = PRService(store=service.store).get_branch_pr_status(target_branch)
            if pr:
                projection.pr_number = pr.number
                projection.pr_status = pr.state.value
                projection.pr_is_draft = pr.draft
                projection.pr_url = pr.url
        except Exception as e:
            projection.pr_fetch_error = str(e)

        _render_snapshot_format(projection, flow_status, output_format)
        return

    # Build timeline using resolver's source-aware flow_status
    # Do NOT call service.get_flow_timeline (reads from local)
    from vibe3.models.data_source import DataSource

    # Use data_source alone to decide timeline source
    # For remote-sourced data (ISSUE_BODY_FALLBACK), always use remote timeline
    # even if empty - never fall back to local events
    if flow_status.data_source == DataSource.ISSUE_BODY_FALLBACK:
        events = _timeline_to_flow_events(flow_status.timeline, target_branch)
    else:
        # Local mode: read from SQLite
        events_data = service.store.get_events(target_branch, limit=100)
        from vibe3.models.flow import FlowEvent

        events = [FlowEvent(**e) for e in events_data]

    if not flow_status:
        logger.error(f"Flow not found: {target_branch}")
        raise typer.Exit(1)

    # Collect issue numbers for title fetching
    issue_numbers = _collect_timeline_issue_numbers(flow_status)

    # Fetch issue titles using projection service
    issue_titles: dict[int, str] = {}
    if issue_numbers:
        projection_service = FlowProjectionService(store=service.store)
        issue_titles, _ = projection_service.get_issue_titles(list(issue_numbers))

    if output_format in ("json", "yaml"):
        # Apply filtering for structured output
        from vibe3.ui.flow_ui_timeline import _filter_passive_if_active_exists

        filtered_events = events
        filtered_events = _filter_passive_if_active_exists(filtered_events)
        if not show_all:
            filtered_events = [
                e
                for e in filtered_events
                if not (e.actor and e.actor.startswith("orchestra:"))
            ]
        if actor_filter:
            import fnmatch

            filtered_events = [
                e
                for e in filtered_events
                if e.actor and fnmatch.fnmatch(e.actor.lower(), actor_filter.lower())
            ]
        json_data = {
            "state": flow_status.model_dump(),
            "events": [e.model_dump() for e in filtered_events],
        }
        if output_format == "json":
            typer.echo(json.dumps(json_data, indent=2, default=str))
        else:
            typer.echo(
                _get_yaml().dump(
                    json_data, default_flow_style=False, allow_unicode=True
                )
            )
    else:
        parent_branch = find_parent_branch(target_branch)
        render_flow_timeline(
            flow_status,
            events,
            parent_branch=parent_branch,
            issue_titles=issue_titles,
            show_all=show_all,
            actor_filter=actor_filter,
        )
        if flow_status.task_issue_number is None:
            hint = build_bind_task_hint()
            console.print(f"[yellow]提示：当前 flow 还没有 task，建议 {hint}[/]")
        return


def status(
    all_flows: AllOption = False,
    check: Annotated[
        bool,
        typer.Option("--check", help="显示前先运行完整 vibe3 check"),
    ] = False,
    output_format: FormatOption = "table",
    trace: TraceOption = False,
    min_ms: TraceMinMsOption = None,
    json_output: Annotated[
        bool,
        typer.Option(
            "--json",
            help="[DEPRECATED] Use --format json instead",
            hidden=True,
        ),
    ] = False,
) -> None:
    """Show dashboard of all active flows.

    By default only shows active flows. Use --all to include done/aborted/stale.
    """
    validate_trace_options(trace, min_ms)
    if trace:
        enable_method_trace(min_ms=min_ms)

    # Handle deprecated --json flag
    if json_output and output_format == "table":
        typer.echo(
            "Warning: --json is deprecated, use --format json instead",
            err=True,
        )
        output_format = "json"
    if check:
        run_full_check_shortcut()

    service = FlowService()
    flows = service.list_flows(status=None if all_flows else "active")

    if output_format in ("json", "yaml"):
        output_data = [f.model_dump() for f in flows]
        if output_format == "json":
            typer.echo(json.dumps(output_data, indent=2, default=str))
        else:  # yaml
            import yaml

            typer.echo(
                yaml.dump(output_data, default_flow_style=False, allow_unicode=True)
            )
        return
    if not flows:
        typer.echo("No active flows")
        raise typer.Exit(0)

    # Try to fetch cached issue titles from orchestra server first
    from vibe3.services import OrchestraStatusService

    config = load_orchestra_config()
    orch_snapshot = OrchestraStatusService.fetch_live_snapshot(config)

    # Use projection service to fetch issue titles (fallback if server not running)
    projection_service = FlowProjectionService()
    issue_numbers = set()
    for flow in flows:
        if flow.task_issue_number:
            issue_numbers.add(flow.task_issue_number)

    titles, net_err = _fetch_issue_titles_for_status(
        flows, projection_service, orch_snapshot, issue_numbers
    )

    # Batch fetch all PRs (1 API call instead of N)
    worktree_map = _fetch_worktree_map()
    pr_map = _fetch_pr_map(flows, projection_service, worktree_map)

    if net_err:
        render_error("网络故障，远端 issue title 不可用（本地数据仍显示）")
    render_flows_status_dashboard(flows, titles, pr_map, worktree_map)


def register_status_commands(app: typer.Typer) -> None:
    """Register flow status commands."""
    app.command(name="show")(show)
    app.command(name="status")(status)
