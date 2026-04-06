"""Issue failure and block side effects service.

This module handles failure/block transitions for issues when
executor or manager runs fail or make no progress.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

from vibe3.clients.github_client import GitHubClient
from vibe3.models.orchestration import IssueState
from vibe3.services.label_service import LabelService
from vibe3.services.ready_close_service import ReadyCloseService

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


def resume_blocked_issue_to_ready(
    *,
    issue_number: int,
    repo: str | None,
    reason: str,
    actor: str = "human:resume",
) -> None:
    """Resume a blocked issue back to ready after blockage resolved.

    Args:
        issue_number: GitHub issue number
        repo: Repository (owner/repo format, optional)
        reason: Resume reason to include in comment
        actor: Actor performing the resume
    """
    GitHubClient().add_comment(
        issue_number,
        "[resume] 已从 state/blocked 恢复到 state/ready。\n\n"
        "阻塞已解除,准备继续执行。\n\n"
        f"原因:{reason}",
        repo=repo,
    )
    LabelService(repo=repo).confirm_issue_state(
        issue_number,
        IssueState.READY,
        actor=actor,
        force=True,  # Force transition from BLOCKED to READY
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


def close_ready_issue(
    *,
    issue_number: int,
    repo: str | None,
    reason: str,
    actor: str = "agent:manager",
) -> str:
    """Close a ready issue when task should not be executed.

    This is the controlled path for managers to close issues
    in state/ready. Only works when issue is in state/ready.

    Args:
        issue_number: GitHub issue number
        repo: Repository (owner/repo format, optional)
        reason: Reason for closing the issue
        actor: Actor performing the close (defaults to "agent:manager")

    Returns:
        Result string: "closed", "already_closed", or "failed"
    """
    # Validate current state
    issue_payload = GitHubClient().view_issue(issue_number, repo=repo)
    if not isinstance(issue_payload, dict):
        logger.bind(
            domain="orchestra",
            issue_number=issue_number,
        ).error("Cannot close issue: failed to fetch issue payload")
        return "failed"

    labels = issue_payload.get("labels", [])
    if not isinstance(labels, list):
        labels = []

    label_names = [lb.get("name", "") for lb in labels if isinstance(lb, dict)]

    # Enforce state/ready requirement
    if IssueState.READY.to_label() not in label_names:
        logger.bind(
            domain="orchestra",
            issue_number=issue_number,
            current_labels=label_names,
        ).error(
            "Cannot close issue: not in state/ready. "
            "Close is only allowed for ready-state issues."
        )
        return "failed"

    # Check if already closed
    if issue_payload.get("state") == "closed":
        logger.bind(
            domain="orchestra",
            issue_number=issue_number,
        ).info("Issue already closed")
        return "already_closed"

    # Close the issue via ReadyCloseService
    close_svc = ReadyCloseService(github=GitHubClient(), repo=repo)
    result = close_svc.close_ready_issue(
        issue_number=issue_number,
        closing_comment=f"[manager] 任务关闭。\n\n原因:{reason}",
    )

    if result == "closed":
        logger.bind(
            domain="orchestra",
            issue_number=issue_number,
        ).info("Issue closed successfully")
    else:
        logger.bind(
            domain="orchestra",
            issue_number=issue_number,
        ).error("Failed to close issue")

    return result
