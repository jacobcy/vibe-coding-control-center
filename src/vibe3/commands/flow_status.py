"""Flow status commands - show, status."""

import json
from typing import TYPE_CHECKING, Annotated

import typer
from loguru import logger

from vibe3.commands.command_options import (
    ActorFilterOption,
    FormatOption,
    SourceOption,
)
from vibe3.commands.common import run_full_check_shortcut, trace_scope
from vibe3.commands.flow_status_helpers import (
    _collect_timeline_issue_numbers,
    _fetch_issue_titles_for_status,
    _fetch_pr_map,
    _fetch_worktree_map,
    _get_yaml,
    _render_snapshot_format,
)
from vibe3.config.orchestra_settings import load_orchestra_config
from vibe3.exceptions import SystemError, UserError
from vibe3.services.flow_projection_service import FlowProjectionService
from vibe3.services.flow_service import FlowService
from vibe3.services.task_binding_guard import build_bind_task_hint
from vibe3.ui.console import console
from vibe3.ui.flow_ui import (
    render_error,
    render_flow_timeline,
    render_flows_status_dashboard,
)
from vibe3.utils.branch_utils import find_parent_branch
from vibe3.utils.issue_branch_resolver import resolve_issue_branch_input

if TYPE_CHECKING:
    pass


from vibe3.commands.command_options import (
    AllOption,
    TraceOption,
)

StatusOption = Annotated[bool, typer.Option("--snapshot", help="静态快照模式")]


def show(
    branch: Annotated[
        str | None,
        typer.Argument(help="Branch name"),
    ] = None,
    snapshot: StatusOption = False,
    trace: TraceOption = False,
    output_format: FormatOption = "table",
    source: SourceOption = "auto",
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
    # Handle deprecated --json flag
    if json_output and output_format == "table":
        typer.echo(
            "Warning: --json is deprecated, use --format json instead",
            err=True,
        )
        output_format = "json"

    with trace_scope(trace, "flow show", domain="flow"):
        service = FlowService()
        if branch:
            try:
                target_branch = resolve_issue_branch_input(branch, service) or branch
            except (UserError, SystemError) as error:
                typer.echo(f"Error: {error}", err=True)
                raise typer.Exit(1) from error
        else:
            target_branch = service.get_current_branch()

        # Get task issue number for remote fallback
        links = service.store.get_issue_links(target_branch)
        task_issue_number = next(
            (link["issue_number"] for link in links if link["issue_role"] == "task"),
            None,
        )

        # Use resolver for source-aware read
        from vibe3.services.flow_status_resolver import FlowStatusResolver

        resolver = FlowStatusResolver(store=service.store)
        flow_status = resolver.resolve(
            branch=target_branch,
            source=source,
            issue_number=task_issue_number,
        )

        # Handle non-registered flow or special branches
        if not flow_status or flow_status.flow_status == "aborted":
            if output_format == "table":
                from vibe3.services.flow_service import FlowService as FlowService_

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
            projection_service = FlowProjectionService()
            projection = projection_service.get_projection(target_branch)
            # Use flow_status from resolver (already set above)
            _render_snapshot_format(projection, flow_status, output_format)
            return

        timeline = service.get_flow_timeline(target_branch)
        if not timeline["state"]:
            logger.error(f"Flow not found: {target_branch}")
            raise typer.Exit(1)

        # Collect issue numbers for title fetching
        issue_numbers = _collect_timeline_issue_numbers(timeline["state"])

        # Fetch issue titles using projection service
        issue_titles: dict[int, str] = {}
        if issue_numbers:
            projection_service = FlowProjectionService(store=service.store)
            issue_titles, _ = projection_service.get_issue_titles(list(issue_numbers))

        if output_format in ("json", "yaml"):
            # Apply filtering for structured output
            from vibe3.ui.flow_ui_timeline import _filter_passive_if_active_exists

            filtered_events = timeline["events"]
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
                    if e.actor
                    and fnmatch.fnmatch(e.actor.lower(), actor_filter.lower())
                ]
            json_data = {
                "state": timeline["state"].model_dump(),
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
                timeline["state"],
                timeline["events"],
                parent_branch=parent_branch,
                issue_titles=issue_titles,
                show_all=show_all,
                actor_filter=actor_filter,
            )
            if timeline["state"].task_issue_number is None:
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
    # Handle deprecated --json flag
    if json_output and output_format == "table":
        typer.echo(
            "Warning: --json is deprecated, use --format json instead",
            err=True,
        )
        output_format = "json"
    with trace_scope(trace, "flow status", domain="flow"):
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
        from vibe3.services.orchestra_status_service import OrchestraStatusService

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
