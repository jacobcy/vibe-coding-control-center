"""Label utility functions."""

from __future__ import annotations

import functools
from typing import TYPE_CHECKING

from loguru import logger

from vibe3.clients import GhIssueLabelPort, TriggerableRoleDefinitionProtocol
from vibe3.models import OrchestraConfig

if TYPE_CHECKING:
    from vibe3.models import IssueInfo


def normalize_labels(raw_labels: object) -> list[str]:
    """Extract label names from GitHub issue payload labels field."""
    if not isinstance(raw_labels, list):
        return []
    result: list[str] = []
    for item in raw_labels:
        if isinstance(item, dict):
            name = item.get("name")
            if isinstance(name, str):
                result.append(name)
    return result


def normalize_assignees(raw_assignees: object) -> list[str]:
    """Extract assignee logins from GitHub issue payload assignees field."""
    if not isinstance(raw_assignees, list):
        return []
    assignees: list[str] = []
    for item in raw_assignees:
        if isinstance(item, dict):
            login = item.get("login")
            if isinstance(login, str) and login:
                assignees.append(login)
    return assignees


def has_manager_assignee(
    assignees: list[str],
    manager_usernames: list[str] | tuple[str, ...],
) -> bool:
    """Whether issue assignees still include a configured manager username.

    Returns True if manager_usernames is empty (no restriction configured).
    This prevents all issues from being filtered out when no managers are configured.
    """
    if not manager_usernames:
        return True  # No restriction: all issues allowed
    return any(assignee in manager_usernames for assignee in assignees)


@functools.lru_cache(maxsize=8)
def _make_dispatch_policy(
    supervisor_label: str,
    manager_usernames: tuple[str, ...],
) -> "object":
    from vibe3.services.issue_dispatch_policy import IssueDispatchPolicy

    return IssueDispatchPolicy(
        supervisor_label=supervisor_label,
        manager_usernames=manager_usernames,
    )


def should_skip_from_queue(
    issue: IssueInfo,
    *,
    supervisor_label: str,
    manager_usernames: list[str] | tuple[str, ...],
    require_manager_assignee: bool = True,
) -> bool:
    """Check whether an issue should be skipped from dispatch queue.

    Issues are skipped if:
    1. They have the supervisor label (managed by supervisor, not auto-dispatch)
    2. They don't have a manager assignee (when required for this queue stage)
    3. They are roadmap/rfc (human discussion, not ready for execution)
    4. They are roadmap/epic (scope too large, needs decomposition)

    Args:
        issue: Issue information
        supervisor_label: Label name for supervisor issues (from config)
        manager_usernames: List of manager usernames (from config)
        require_manager_assignee: Whether this queue stage still requires the
            issue to be assigned to a manager username. Entry-point ready issues
            do; downstream state-label dispatch does not.

    Returns:
        True if issue should be skipped, False otherwise
    """
    from vibe3.services.issue_dispatch_policy import IssueDispatchPolicy

    policy: IssueDispatchPolicy = _make_dispatch_policy(  # type: ignore[assignment]
        supervisor_label, tuple(manager_usernames)
    )
    reasons = policy.exclusion_reasons(issue)
    if require_manager_assignee:
        return bool(reasons)

    # Keep the legacy "skip" behavior for non-assignee exclusions only.
    assignee_only_codes = {"missing_manager_assignee", "non_manager_assignee"}
    return any(reason.code not in assignee_only_codes for reason in reasons)


def clean_old_state_labels(
    issue: "IssueInfo",
    role: TriggerableRoleDefinitionProtocol,
    config: OrchestraConfig,
) -> None:
    """Remove conflicting state/* labels before dispatch.

    Args:
        issue: Issue to clean labels for
        role: Role definition for this dispatch
        config: Orchestra configuration
    """
    old_state_labels = [
        lb
        for lb in issue.labels
        if lb.startswith("state/") and lb != role.trigger_state.to_label()
    ]
    if old_state_labels:
        try:
            label_port = GhIssueLabelPort(repo=config.repo)
            for old_lb in old_state_labels:
                label_port.remove_issue_label(issue.number, old_lb)
        except Exception as exc:
            logger.bind(domain="orchestra").warning(
                f"Failed to clean old state labels for #{issue.number}: {exc}"
            )


# ---------------------------------------------------------------------------
# Remote label audit — pure detection functions (no I/O)
# ---------------------------------------------------------------------------

# Execution states that require an active local flow
_EXECUTION_STATES = frozenset(
    {
        "merge-ready",
        "review",
        "in-progress",
        "handoff",
        "claimed",
    }
)

# State priority for Rule 2 (index 0 = highest)
_STATE_PRIORITY = [
    "blocked",
    "done",
    "merge-ready",
    "review",
    "in-progress",
    "handoff",
    "claimed",
    "ready",
]


def audit_roadmap_state_conflict(labels: list[str]) -> list[str]:
    """Rule 1: roadmap/rfc|epic + state/* → remove all state labels.

    Returns state labels that should be removed, or empty list if no conflict.
    """
    has_roadmap = "roadmap/rfc" in labels or "roadmap/epic" in labels
    if not has_roadmap:
        return []
    return [lb for lb in labels if lb.startswith("state/")]


def audit_multiple_state_labels(labels: list[str]) -> list[str]:
    """Rule 2: multiple state/* → keep highest priority, remove others.

    Returns lower-priority state labels to remove.
    """
    state_labels = [lb for lb in labels if lb.startswith("state/")]
    if len(state_labels) <= 1:
        return []

    best, best_idx = None, len(_STATE_PRIORITY)
    for lb in state_labels:
        name = lb.replace("state/", "")
        if name in _STATE_PRIORITY:
            idx = _STATE_PRIORITY.index(name)
            if idx < best_idx:
                best_idx, best = idx, lb

    if best is None:
        return []  # unknown states, skip
    return [lb for lb in state_labels if lb != best]


def audit_orphan_execution_state(
    labels: list[str],
    *,
    has_local_flow: bool,
) -> tuple[list[str], list[str]]:
    """Rule 3: manager issue with execution state but no local flow.

    Returns (labels_to_remove, labels_to_add).
    """
    if has_local_flow:
        return ([], [])
    execution_labels = [
        lb
        for lb in labels
        if lb.startswith("state/") and lb.replace("state/", "") in _EXECUTION_STATES
    ]
    if not execution_labels:
        return ([], [])
    return (execution_labels, ["state/ready"])


def audit_orphan_orchestra_governed(labels: list[str]) -> list[str]:
    """Rule 4: orchestra-governed without state/* or roadmap → remove it.

    Returns labels to remove, or empty list.
    """
    if "orchestra-governed" not in labels:
        return []
    has_state = any(lb.startswith("state/") for lb in labels)
    has_roadmap = "roadmap/rfc" in labels or "roadmap/epic" in labels
    if has_state or has_roadmap:
        return []
    return ["orchestra-governed"]
