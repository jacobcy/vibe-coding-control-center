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
