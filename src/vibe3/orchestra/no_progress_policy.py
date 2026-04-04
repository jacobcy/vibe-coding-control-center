"""Manager no-progress blocking policy.

This module provides the explicit policy for auto-blocking issues when
a manager session completes without observable progress.

Current mainline behavior:
- Manager is the flow owner
- Manager no-progress currently means blocked
- Blocked follow-up (doctor/aborted) is intentionally outside current scope
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

from vibe3.models.orchestration import IssueState

if TYPE_CHECKING:
    from vibe3.clients.github_client import GitHubClient


def should_auto_block(
    issue_number: int,
    current_labels: list[str],
    has_live_session: bool,
    state_changed: bool,
) -> bool:
    """Determine if issue should be auto-blocked.

    Args:
        issue_number: GitHub issue number
        current_labels: Current issue labels
        has_live_session: Whether manager session is still alive
        state_changed: Whether state label changed during manager run

    Returns:
        True if issue should be auto-blocked, False otherwise
    """
    # Do not block if session is still alive
    if has_live_session:
        return False

    # Do not block if state already changed (manager made progress)
    if state_changed:
        return False

    # Do not block if already blocked
    if IssueState.BLOCKED.to_label() in current_labels:
        return False

    # Block if session ended without state change
    return True


def execute_auto_block(
    issue_number: int,
    current_labels: list[str],
    github: GitHubClient,
    repo: str | None = None,
) -> None:
    """Execute the auto-block action.

    Adds block comment and transitions issue from ready to blocked state.

    Args:
        issue_number: GitHub issue number
        current_labels: Current issue labels (used for skip check)
        github: GitHub client for API calls
        repo: Optional repository (owner/repo format)
    """
    import subprocess

    # Double-check: skip if already blocked
    if IssueState.BLOCKED.to_label() in current_labels:
        logger.bind(
            domain="orchestra",
            issue=issue_number,
        ).debug(
            "Issue already blocked, skipping auto-block"
        )
        return

    logger.bind(
        domain="orchestra",
        issue=issue_number,
    ).warning(
        f"Manager session ended without state change, "
        f"auto-blocking issue #{issue_number}"
    )

    # Add block comment
    reason = (
        "Manager 执行完成但未改变状态。可能原因：\n"
        "- Scene 不健康或无法恢复\n"
        "- 缺少必要的前置条件（如 spec_ref）\n"
        "- 需要人工决策或额外信息\n\n"
        "需要人工介入处理后，移除 state/blocked 标签以重新触发。"
    )
    github.add_comment(issue_number, f"[dispatcher] {reason}")

    # Update labels: remove ready, add blocked
    cmd = [
        "gh",
        "issue",
        "edit",
        str(issue_number),
        "--add-label",
        IssueState.BLOCKED.to_label(),
        "--remove-label",
        IssueState.READY.to_label(),
    ]
    if repo:
        cmd.extend(["--repo", repo])

    try:
        subprocess.run(cmd, capture_output=True, text=True, timeout=15, check=False)
    except Exception as exc:
        logger.bind(
            domain="orchestra",
            issue=issue_number,
        ).error(f"Failed to update labels: {exc}")
        raise