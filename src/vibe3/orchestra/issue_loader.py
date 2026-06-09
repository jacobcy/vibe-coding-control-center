"""Issue loading and flow context utilities for dispatch coordination."""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

from vibe3.clients import GITHUB_DEFAULT_VIEW_FIELDS
from vibe3.models import OrchestraConfig

if TYPE_CHECKING:
    from vibe3.clients import GitHubClient, SQLiteClient
    from vibe3.models import IssueInfo
    from vibe3.orchestra import FlowManagerProtocol


def is_auto_task_branch(branch: str) -> bool:
    """Check if branch is an auto-task branch.

    Args:
        branch: Branch name to check

    Returns:
        True if branch starts with 'task/issue-'
    """
    return branch.startswith("task/issue-")


def get_flow_context(
    issue_number: int,
    config: OrchestraConfig,
    github: "GitHubClient",
    store: "SQLiteClient",
    flow_manager: "FlowManagerProtocol",
) -> tuple[str, dict[str, object] | None]:
    """Get flow context (branch and state) for an issue.

    Args:
        issue_number: Issue number to look up
        config: Orchestra configuration
        github: GitHub client
        store: SQLite client
        flow_manager: Flow manager

    Returns:
        Tuple of (branch, flow_state)
    """
    flow = flow_manager.get_flow_for_issue(issue_number)
    branch = str(flow.get("branch") or "").strip() if flow else ""
    if not branch:
        return "", None
    return branch, store.get_flow_state(branch)


def get_flow_context_bulk(
    issue_numbers: list[int],
    config: OrchestraConfig,
    github: "GitHubClient",
    store: "SQLiteClient",
    flow_manager: "FlowManagerProtocol",
) -> dict[int, tuple[str, dict[str, object] | None]]:
    """Batch get flow context (branch and state) for multiple issues.

    Reduces N+1 queries to 2 bulk queries by:
    1. Bulk-fetching all flow mappings for the issue numbers
    2. Bulk-fetching flow states for the resolved branches

    Args:
        issue_numbers: Issue numbers to look up
        config: Orchestra configuration
        github: GitHub client
        store: SQLite client
        flow_manager: Flow manager

    Returns:
        Dict mapping issue_number -> (branch, flow_state).
        Issues with no flow get ("", None).
    """
    if not issue_numbers:
        return {}

    # Step 1: Bulk fetch flow mappings
    flows_by_issue = store.get_flows_by_issues_bulk(issue_numbers, role="task")

    # Resolve each issue to its best flow (replicates find_active_flow logic)
    issue_to_flow: dict[int, dict[str, object] | None] = {}
    branches_to_fetch: set[str] = set()
    for issue_num, flows in flows_by_issue.items():
        best = flow_manager.resolve_best_flow(issue_num, flows)
        issue_to_flow[issue_num] = best
        if best:
            branch = str(best.get("branch") or "").strip()
            if branch:
                branches_to_fetch.add(branch)

    # Step 2: Bulk fetch flow states for all resolved branches
    flow_states = store.get_flow_state_bulk(list(branches_to_fetch))

    # Step 3: Assemble result
    result: dict[int, tuple[str, dict[str, object] | None]] = {}
    for issue_num in issue_numbers:
        flow = issue_to_flow.get(issue_num)
        if flow is None:
            result[issue_num] = ("", None)
            continue
        branch = str(flow.get("branch") or "").strip()
        if not branch:
            result[issue_num] = ("", None)
            continue
        result[issue_num] = (branch, flow_states.get(branch))

    return result


def load_issue(
    issue_number: int, config: OrchestraConfig, github: "GitHubClient"
) -> "IssueInfo | None":
    """Load the current issue snapshot for an already-frozen issue."""
    from vibe3.models import IssueInfo

    try:
        payload = github.view_issue(
            issue_number, repo=config.repo, fields=list(GITHUB_DEFAULT_VIEW_FIELDS)
        )
    except Exception as exc:
        logger.bind(domain="global_dispatch", issue=issue_number).error(
            f"view_issue failed for #{issue_number}: {exc}"
        )
        return None
    if not isinstance(payload, dict):
        return None
    return IssueInfo.from_github_payload(payload)
