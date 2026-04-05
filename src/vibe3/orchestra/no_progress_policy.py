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
    from vibe3.clients.sqlite_client import SQLiteClient


def _extract_issue_state_label(issue_payload: dict[str, object]) -> str | None:
    """Extract state label from GitHub issue payload."""
    labels = issue_payload.get("labels")
    if not isinstance(labels, list):
        return None
    for label in labels:
        if not isinstance(label, dict):
            continue
        name = label.get("name")
        if isinstance(name, str) and name.startswith("state/"):
            return name
    return None


def _comment_count(issue_payload: dict[str, object]) -> int:
    """Return comment count from GitHub issue payload."""
    comments = issue_payload.get("comments")
    return len(comments) if isinstance(comments, list) else 0


def snapshot_progress(
    *,
    issue_number: int,
    branch: str,
    store: SQLiteClient,
    github: GitHubClient,
    repo: str | None = None,
) -> dict[str, object]:
    """Capture a snapshot of observable progress signals.

    This is the shared progress contract used by both async runtime
    and sync manager execution paths.

    Args:
        issue_number: GitHub issue number
        branch: Flow branch name
        store: SQLite client for flow state
        github: GitHub client for issue data
        repo: Optional repository (owner/repo format)

    Returns:
        Dict with progress signal values for comparison
    """
    # Get issue payload
    issue_payload = github.view_issue(issue_number, repo=repo)
    if not isinstance(issue_payload, dict):
        issue_payload = {}

    from vibe3.clients.git_client import GitClient
    from vibe3.utils.git_helpers import get_branch_handoff_dir

    # Get flow state refs
    flow_state = store.get_flow_state(branch) if branch else {}
    state_dict = flow_state or {}
    refs = (
        state_dict.get("spec_ref"),
        state_dict.get("plan_ref"),
        state_dict.get("report_ref"),
        state_dict.get("audit_ref"),
        state_dict.get("next_step"),
        state_dict.get("blocked_by"),
    )

    try:
        git_dir = GitClient().get_git_common_dir()
        handoff_dir = get_branch_handoff_dir(git_dir, branch) if git_dir else None
    except Exception:
        handoff_dir = None

    handoff_sig = None
    if handoff_dir:
        handoff_file = handoff_dir / "current.md"
        if handoff_file.exists():
            stat = handoff_file.stat()
            handoff_sig = (True, int(stat.st_mtime_ns), int(stat.st_size))

    return {
        "state_label": _extract_issue_state_label(issue_payload),
        "comment_count": _comment_count(issue_payload),
        "handoff": handoff_sig,
        "refs": refs,
    }


def has_progress_changed(
    before: dict[str, object],
    after: dict[str, object],
) -> bool:
    """Check if any progress signal changed between snapshots.

    Args:
        before: Previous progress snapshot
        after: Current progress snapshot

    Returns:
        True if any signal changed (progress was made)
    """
    return any(
        before[key] != after[key]
        for key in ("state_label", "comment_count", "handoff", "refs")
    )


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
    source_state_label: str = IssueState.READY.to_label(),
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
        ).debug("Issue already blocked, skipping auto-block")
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

    # Update labels: remove current trigger state, add blocked
    cmd = [
        "gh",
        "issue",
        "edit",
        str(issue_number),
        "--add-label",
        IssueState.BLOCKED.to_label(),
        "--remove-label",
        source_state_label,
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
