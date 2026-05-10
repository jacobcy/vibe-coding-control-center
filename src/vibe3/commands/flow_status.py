"""Flow status commands - show, status."""

import json
import re
from typing import TYPE_CHECKING, Annotated, Any

import typer
from loguru import logger

from vibe3.commands.command_options import ActorFilterOption, FormatOption
from vibe3.commands.common import run_full_check_shortcut, trace_scope
from vibe3.config.orchestra_settings import load_orchestra_config
from vibe3.exceptions import SystemError, UserError
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
from vibe3.utils.branch_utils import find_parent_branch
from vibe3.utils.issue_branch_resolver import resolve_issue_branch_input

if TYPE_CHECKING:
    pass


from vibe3.commands.command_options import (
    AllOption,
    JsonOption,
    TraceOption,
)

StatusOption = Annotated[bool, typer.Option("--snapshot", help="静态快照模式")]


def _render_snapshot_format(projection: Any, flow_status: Any, format: str) -> None:
    """Render snapshot output in json/yaml/table format."""
    output_data = {
        "branch": projection.branch,
        "flow_slug": projection.flow_slug,
        "flow_status": projection.flow_status,
        "task_issue_number": projection.task_issue_number,
        "pr_number": projection.pr_number,
        "spec_ref": projection.spec_ref,
        "blocked_by": projection.blocked_by,
        "next_step": projection.next_step,
        "offline_mode": projection.offline_mode,
        "pr_status": projection.pr_status,
        "pr_is_draft": projection.pr_is_draft,
        "pr_url": projection.pr_url,
    }
    if format == "json":
        typer.echo(json.dumps(output_data, indent=2, default=str))
    elif format == "yaml":
        import yaml

        typer.echo(yaml.dump(output_data, default_flow_style=False, allow_unicode=True))
    else:
        if not flow_status:
            logger.error("Flow not found")
            raise typer.Exit(1)
        projection_service = FlowProjectionService()
        issue_numbers = {flow_status.task_issue_number} | {
            link.issue_number for link in flow_status.issues
        }
        issue_titles, network_error = projection_service.get_issue_titles(
            list(issue_numbers)
        )
        pr_data = (
            {
                "number": projection.pr_number,
                "state": projection.pr_status,
                "draft": projection.pr_is_draft,
                "url": projection.pr_url,
            }
            if projection.pr_number and not projection.pr_fetch_error
            else None
        )
        if network_error or projection.hydrate_error or projection.pr_fetch_error:
            render_error("网络故障，远端 issue/PR 信息不可用（本地数据仍显示）")
        render_flow_status(
            flow_status,
            issue_titles,
            pr_data,
            parent_branch=find_parent_branch(projection.branch),
            worktree_root=flow_status.worktree_root,
        )


def _fetch_worktree_map() -> dict[str, str]:
    """Fetch worktree mapping from git worktree list."""
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
    return worktree_map


def _fetch_pr_map(
    flows: list[Any],
    projection_service: FlowProjectionService,
    worktree_map: dict[str, str],
) -> dict[str, dict[str, object]]:
    """Batch fetch all PRs for flows."""
    try:
        all_prs = projection_service.pr_service.github_client.list_all_prs(state="open")
        branch_to_pr = {pr.head_branch: pr for pr in all_prs}
        return {
            flow.branch: {
                "number": pr.number,
                "title": pr.title,
                "state": pr.state.value,
                "draft": pr.draft,
                "url": pr.url,
                "worktree": worktree_map.get(flow.branch),
            }
            for flow in flows
            if (pr := branch_to_pr.get(flow.branch))
        }
    except Exception as exc:
        logger.bind(domain="flow").warning(f"Failed to fetch PRs: {exc}")
        return {}


def _fetch_issue_titles_for_status(
    flows: list[Any],
    projection_service: FlowProjectionService,
    orch_snapshot: Any,
    issue_numbers: set[int],
) -> tuple[dict[int, str], bool]:
    """Fetch issue titles for flow status dashboard."""
    if orch_snapshot and orch_snapshot.server_running:
        titles = {
            entry.number: entry.title
            for entry in orch_snapshot.active_issues
            if entry.number in issue_numbers
        }
        missing = issue_numbers - set(titles.keys())
        if missing:
            extra_titles, net_err = projection_service.get_issue_titles(list(missing))
            titles.update(extra_titles)
            return titles, net_err
        return titles, False

    # Server not running, use cache service with real branches
    from vibe3.services.issue_title_cache_service import IssueTitleCacheService

    branches = [flow.branch for flow in flows if flow.branch]
    title_cache = IssueTitleCacheService(
        store=projection_service.store, github_client=projection_service.github_client
    )
    branch_titles, net_err = title_cache.get_titles_with_fallback(branches)
    titles = {
        flow.task_issue_number: branch_titles[flow.branch]
        for flow in flows
        if flow.task_issue_number and flow.branch in branch_titles
    }
    return titles, net_err


def _collect_timeline_issue_numbers(state: Any) -> set[int]:
    """Collect issue numbers from timeline state for title fetching."""
    issue_numbers = {state.task_issue_number} if state.task_issue_number else set()
    issue_numbers.update(link.issue_number for link in state.issues)
    if state.spec_ref and (match := re.match(r"^#?(\d+)$", state.spec_ref.strip())):
        issue_numbers.add(int(match.group(1)))
    return issue_numbers


def show(
    branch: Annotated[
        str | None,
        typer.Argument(help="Branch name"),
    ] = None,
    snapshot: StatusOption = False,
    trace: TraceOption = False,
    format: FormatOption = "table",
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
    """Show flow details."""
    # Handle deprecated --json flag
    if json_output and format == "table":
        typer.echo(
            "Warning: --json is deprecated, use --format json instead",
            err=True,
        )
        format = "json"

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

        flow_status = service.get_flow_status(target_branch)

        # Handle non-registered flow or special branches
        if not flow_status or flow_status.flow_status == "aborted":
            if format == "table":
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
                    if format == "json":
                        typer.echo(json.dumps(output_data))
                    else:
                        import yaml

                        typer.echo(
                            yaml.dump(
                                output_data,
                                default_flow_style=False,
                                allow_unicode=True,
                            )
                        )
                    raise typer.Exit(1)

        if snapshot:
            projection_service = FlowProjectionService()
            projection = projection_service.get_projection(target_branch)
            flow_status = service.get_flow_status(target_branch)
            _render_snapshot_format(projection, flow_status, format)
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

        if format in ("json", "yaml"):
            json_data = {
                "state": timeline["state"].model_dump(),
                "events": [e.model_dump() for e in timeline["events"]],
            }
            if format == "json":
                typer.echo(json.dumps(json_data, indent=2, default=str))
            else:
                import yaml

                typer.echo(
                    yaml.dump(json_data, default_flow_style=False, allow_unicode=True)
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
    json_output: JsonOption = False,
    trace: TraceOption = False,
) -> None:
    """Show dashboard of all active flows.

    By default only shows active flows. Use --all to include done/aborted/stale.
    """
    with trace_scope(trace, "flow status", domain="flow"):
        if check:
            run_full_check_shortcut()

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
