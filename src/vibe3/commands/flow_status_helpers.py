"""Helper functions for flow_status commands."""

import json
import re
from types import ModuleType
from typing import TYPE_CHECKING, Any

import typer
from loguru import logger

from vibe3.exceptions import UserError
from vibe3.services import FlowProjectionService
from vibe3.ui import render_error, render_flow_status
from vibe3.utils import find_parent_branch

if TYPE_CHECKING:
    from vibe3.models.flow import FlowEvent, TimelineEvent


def _parse_remote_issue_number(raw: str) -> int:
    """Parse issue number from raw CLI input for --remote mode."""
    stripped = raw.strip()
    if stripped.isdigit():
        return int(stripped)
    raise UserError(
        f"Cannot parse issue number from: {raw}. " "Provide a numeric issue number."
    )


def _timeline_to_flow_events(
    timeline: list["TimelineEvent"],
    branch: str,
) -> list["FlowEvent"]:
    """Convert TimelineEvent objects to FlowEvent for timeline rendering."""
    from vibe3.models.flow import FlowEvent

    return [
        FlowEvent(
            branch=branch,
            event_type=te.event_type,
            actor=te.actor,
            detail=te.detail,
            created_at=te.timestamp,
        )
        for te in timeline
    ]


def _get_yaml() -> ModuleType:
    """Lazy import yaml to avoid unconditional import cost."""
    import yaml

    return yaml


def _render_snapshot_format(
    projection: Any, flow_status: Any, output_format: str
) -> None:
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
    if output_format == "json":
        typer.echo(json.dumps(output_data, indent=2, default=str))
    elif output_format == "yaml":
        typer.echo(
            _get_yaml().dump(output_data, default_flow_style=False, allow_unicode=True)
        )
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
        branch_to_pr = projection_service.pr_service.refresh_open_pr_cache()
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
