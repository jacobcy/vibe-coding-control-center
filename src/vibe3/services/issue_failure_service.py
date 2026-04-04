"""Issue failure and block side effects service.

This module handles failure/block transitions for issues when
executor or manager runs fail or make no progress.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vibe3.clients.github_client import GitHubClient
from vibe3.models.orchestration import IssueState
from vibe3.services.label_service import LabelService

if TYPE_CHECKING:
    pass


def fail_executor_issue(
    *,
    issue_number: int,
    reason: str,
    actor: str,
) -> None:
    """Fail an executor issue with comment and state transition.

    Args:
        issue_number: GitHub issue number
        reason: Failure reason to include in comment
        actor: Actor performing the transition (e.g., "agent:executor")
    """
    GitHubClient().add_comment(
        issue_number,
        f"[run] 执行报错,已切换为 state/failed。\n\n原因:{reason}",
    )
    LabelService().confirm_issue_state(
        issue_number,
        IssueState.FAILED,
        actor=actor,
        force=True,
    )


def fail_manager_issue(
    *,
    issue_number: int,
    reason: str,
    actor: str = "agent:manager",
) -> None:
    """Fail a manager issue with comment and state transition.

    Args:
        issue_number: GitHub issue number
        reason: Failure reason to include in comment
        actor: Actor performing the transition (defaults to "agent:manager")
    """
    GitHubClient().add_comment(
        issue_number,
        f"[manager] 管理执行报错,已切换为 state/failed。\n\n原因:{reason}",
    )
    LabelService().confirm_issue_state(
        issue_number,
        IssueState.FAILED,
        actor=actor,
        force=True,
    )


def block_manager_noop_issue(
    *,
    issue_number: int,
    repo: str | None,
    reason: str,
    actor: str,
) -> None:
    """Block a manager issue that made no progress.

    Adds block comment if not already present, and transitions
    issue to blocked state.

    Args:
        issue_number: GitHub issue number
        repo: Repository (owner/repo format, optional)
        reason: Block reason to include in comment
        actor: Actor performing the transition
    """
    issue_payload = GitHubClient().view_issue(issue_number, repo=repo)
    if isinstance(issue_payload, dict) and not _has_matching_block_comment(
        issue_payload, reason
    ):
        GitHubClient().add_comment(
            issue_number,
            "[manager] 无法推进,已切换为 state/blocked。\n\n" f"原因:{reason}",
            repo=repo,
        )
    LabelService(repo=repo).confirm_issue_state(
        issue_number,
        IssueState.BLOCKED,
        actor=actor,
        force=True,
    )


def _has_matching_block_comment(issue_payload: dict[str, object], reason: str) -> bool:
    """Check if issue already has a block comment with this reason.

    Args:
        issue_payload: GitHub issue payload
        reason: Reason string to search for

    Returns:
        True if matching block comment exists
    """
    comments = issue_payload.get("comments")
    if not isinstance(comments, list):
        return False
    for comment in comments:
        if not isinstance(comment, dict):
            continue
        body = comment.get("body")
        if isinstance(body, str) and reason in body:
            return True
    return False
