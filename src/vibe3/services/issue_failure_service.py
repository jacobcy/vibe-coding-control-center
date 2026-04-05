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


def resume_failed_issue_to_handoff(
    *,
    issue_number: int,
    repo: str | None,
    reason: str,
    actor: str = "human:resume",
) -> None:
    """Resume a failed issue back to handoff for manager triage.

    Args:
        issue_number: GitHub issue number
        repo: Repository (owner/repo format, optional)
        reason: Resume reason to include in comment
        actor: Actor performing the resume
    """
    GitHubClient().add_comment(
        issue_number,
        "[resume] 已从 state/failed 继续到 state/handoff。\n\n"
        "manager 将重新判断现场并决定下一步。\n\n"
        f"原因:{reason}",
        repo=repo,
    )
    LabelService(repo=repo).confirm_issue_state(
        issue_number,
        IssueState.HANDOFF,
        actor=actor,
        force=False,
    )


# Backward compatibility alias
recover_failed_issue_to_handoff = resume_failed_issue_to_handoff


def resume_failed_issue_to_ready(
    *,
    issue_number: int,
    repo: str | None,
    reason: str,
    actor: str = "human:resume",
) -> None:
    """Resume a failed issue back to ready for fresh manager entry.

    Args:
        issue_number: GitHub issue number
        repo: Repository (owner/repo format, optional)
        reason: Resume reason to include in comment
        actor: Actor performing the resume
    """
    GitHubClient().add_comment(
        issue_number,
        "[resume] 已从 state/failed 继续到 state/ready。\n\n"
        "将重新进入 manager 标准入口。\n\n"
        f"原因:{reason}",
        repo=repo,
    )
    LabelService(repo=repo).confirm_issue_state(
        issue_number,
        IssueState.READY,
        actor=actor,
        force=True,  # Force transition from FAILED to READY
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


def confirm_plan_handoff(
    *,
    issue_number: int,
    actor: str = "agent:plan",
) -> str:
    """Transition planner issue to handoff after successful plan.

    Args:
        issue_number: GitHub issue number
        actor: Actor performing the transition (defaults to "agent:plan")

    Returns:
        Transition result string (e.g., "advanced" or "blocked")
    """
    return LabelService().confirm_issue_state(
        issue_number,
        IssueState.HANDOFF,
        actor=actor,
    )


def fail_planner_issue(
    *,
    issue_number: int,
    reason: str,
    actor: str = "agent:plan",
) -> None:
    """Fail a planner issue with comment and state transition.

    Args:
        issue_number: GitHub issue number
        reason: Failure reason to include in comment
        actor: Actor performing the transition (defaults to "agent:plan")
    """
    GitHubClient().add_comment(
        issue_number,
        f"[plan] 规划执行报错,已切换为 state/failed。\n\n原因:{reason}",
    )
    LabelService().confirm_issue_state(
        issue_number,
        IssueState.FAILED,
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
