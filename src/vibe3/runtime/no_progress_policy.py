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

from vibe3.models.orchestration import STATE_FALLBACK_MATRIX, IssueState

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

    # Capture major refs in a dict for flexible comparison
    refs = {
        "spec_ref": state_dict.get("spec_ref"),
        "plan_ref": state_dict.get("plan_ref"),
        "report_ref": state_dict.get("report_ref"),
        "audit_ref": state_dict.get("audit_ref"),
        "pr_ref": state_dict.get("pr_ref"),  # PR URL as proof of PR creation
        "next_step": state_dict.get("next_step"),
        "blocked_by": state_dict.get("blocked_by"),
    }

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
        "issue_state": issue_payload.get(
            "state", "open"
        ),  # GitHub issue state: open/closed
        "flow_status": state_dict.get("flow_status"),  # Flow status: active/aborted/etc
    }


def has_progress_changed(
    before: dict[str, object],
    after: dict[str, object],
    expected_ref: str | None = None,
    require_state_transition: bool = False,
    allow_close_as_progress: bool = False,
) -> bool:
    """Check if any progress signal changed between snapshots.

    Args:
        before: Previous progress snapshot
        after: Current progress snapshot
        expected_ref: Optional specific ref key that MUST change to count as progress
        require_state_transition: If True, only state label change counts as progress
        allow_close_as_progress: If True, explicit abandon (flow_status=aborted)
            counts as progress. This applies to READY and HANDOFF manager paths.

    Returns:
        True if progress was made (signals changed as expected)
    """
    # If state label changed, it's definitely a transition (considered progress)
    if before["state_label"] != after["state_label"]:
        return True

    # Explicit abandon detection: flow_status changed to "aborted"
    # This is the key signal that manager intentionally abandoned the flow,
    # distinguishing it from incidental external closure.
    if allow_close_as_progress:
        before_flow_status = before.get("flow_status")
        after_flow_status = after.get("flow_status")
        if before_flow_status != "aborted" and after_flow_status == "aborted":
            return True

    # For states like READY/HANDOFF, we MUST transition to another state.
    # Simple side effects (comments/handoff) do not count as "progress"
    # for these states.
    if require_state_transition:
        return False

    # If a specific ref was expected (strict progress contract for plan/run/review)
    if expected_ref:
        before_refs = before.get("refs")
        after_refs = after.get("refs")
        if not isinstance(before_refs, dict) or not isinstance(after_refs, dict):
            return False
        # Check if the specific expected ref changed
        return before_refs.get(expected_ref) != after_refs.get(expected_ref)

    # General heuristic progress check (for loose states if any)
    return any(
        before[key] != after[key] for key in ("comment_count", "handoff", "refs")
    )


def execute_state_fallback(
    issue_number: int,
    current_labels: list[str],
    github: GitHubClient,
    source_state: IssueState,
    repo: str | None = None,
) -> None:
    """Execute the auto-fallback/block action based on the state machine contract.

    Args:
        issue_number: GitHub issue number
        current_labels: Current issue labels (used for skip check)
        github: GitHub client for API calls
        source_state: The current issue state that failed to progress
        repo: Optional repository (owner/repo format)
    """

    target_state = STATE_FALLBACK_MATRIX.get(source_state, IssueState.BLOCKED)
    target_label = target_state.to_label()
    source_label = source_state.to_label()
    failed_label = IssueState.FAILED.to_label()

    # Execution failures are terminal recovery states for the current run.
    # Never stack a no-progress fallback on top of state/failed.
    if failed_label in current_labels:
        logger.bind(
            domain="orchestra",
            issue=issue_number,
        ).warning(f"Skip fallback for issue #{issue_number}: already in {failed_label}")
        return

    # Double-check: skip if already transitioned or in target state
    if source_label not in current_labels:
        return
    if target_label in current_labels:
        return

    logger.bind(
        domain="orchestra",
        issue=issue_number,
    ).warning(
        f"Session ({source_label}) ended without progress artifacts, "
        f"auto-transitioning issue #{issue_number} to {target_label}"
    )

    # Determine reason message based on target state
    if target_state == IssueState.BLOCKED:
        reason = (
            "Manager 执行完成但未改变状态（no-progress）。可能原因：\n"
            "- Scene 不健康或无法恢复\n"
            "- 缺少必要的前置条件（如 spec_ref）\n"
            "- 需要人工决策或额外信息\n\n"
            "需要人工介入处理后，移除 state/blocked 标签以重新触发。"
        )
    else:
        reason = (
            "执行结束但未产出预期产物（no-progress）。"
            f"已由系统自动回退到 {target_label} 以便重新进入判定环节。\n"
            f"原因：本阶段（{source_label}）未产生有效的 refs / artifacts 变化。"
        )

    # Add comment (with deduplication to avoid spam during retries)
    full_comment = f"[dispatcher] {reason}"
    issue_payload = github.view_issue(issue_number, repo=repo)
    if isinstance(issue_payload, dict) and not _has_matching_comment(
        issue_payload, full_comment
    ):
        github.add_comment(issue_number, full_comment, repo=repo)

    # Use LabelService for atomic state transition with validation
    from vibe3.services.label_service import LabelService

    try:
        result = LabelService(repo=repo).confirm_issue_state(
            issue_number,
            target_state,
            actor="orchestra:fallback",
            force=True,  # Force if needed, but matrix should already allow this
        )
        if result == "blocked":
            raise RuntimeError(
                f"State transition to {target_state.value} was blocked by state machine"
            )
    except Exception as exc:
        logger.bind(
            domain="orchestra",
            issue=issue_number,
        ).error(f"Failed to update labels during fallback: {exc}")
        raise


def _has_matching_comment(issue_payload: dict[str, object], comment_text: str) -> bool:
    """Check if issue already has an identical comment.

    Args:
        issue_payload: GitHub issue payload
        comment_text: Comment text to search for

    Returns:
        True if matching comment exists
    """
    comments = issue_payload.get("comments")
    if not isinstance(comments, list):
        return False
    for comment in comments:
        if not isinstance(comment, dict):
            continue
        body = comment.get("body")
        if isinstance(body, str) and comment_text.strip() == body.strip():
            return True
    return False
