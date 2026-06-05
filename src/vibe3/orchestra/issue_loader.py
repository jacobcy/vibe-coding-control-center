"""Issue loading and flow context utilities for dispatch coordination."""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

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


def load_issue(
    issue_number: int, config: OrchestraConfig, github: "GitHubClient"
) -> "IssueInfo | None":
    """Load the current issue snapshot for an already-frozen issue."""
    from vibe3.models import IssueInfo

    try:
        payload = github.view_issue(issue_number, repo=config.repo)
    except Exception as exc:
        logger.bind(domain="global_dispatch", issue=issue_number).error(
            f"view_issue failed for #{issue_number}: {exc}"
        )
        return None
    if not isinstance(payload, dict):
        return None
    return IssueInfo.from_github_payload(payload)
