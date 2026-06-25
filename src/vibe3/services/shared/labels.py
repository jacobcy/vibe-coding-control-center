"""Label utility functions."""

from __future__ import annotations

import functools
from typing import TYPE_CHECKING

from loguru import logger

from vibe3.clients import (
    GhIssueLabelPort,
    TriggerableRoleDefinitionProtocol,
    has_manager_assignee,
    normalize_assignees,
    normalize_labels,
)
from vibe3.models import OrchestraConfig

if TYPE_CHECKING:
    from vibe3.models import DispatchExclusion, IssueInfo


# Re-export for backward compatibility
__all__ = [
    "normalize_labels",
    "normalize_assignees",
    "has_manager_assignee",
    "should_skip_from_queue",
]


@functools.lru_cache(maxsize=8)
def _make_dispatch_policy(
    supervisor_label: str,
    manager_usernames: tuple[str, ...],
) -> "object":
    import importlib

    _mod = importlib.import_module("vibe3.services.issue.dispatch_policy")
    return _mod.IssueDispatchPolicy(
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
    policy: object = _make_dispatch_policy(  # type: ignore[assignment]
        supervisor_label, tuple(manager_usernames)
    )
    reasons = policy.exclusion_reasons(issue)  # type: ignore[attr-defined]
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
# Label semantic constants (single source of truth)
# ---------------------------------------------------------------------------

_ROADMAP_LABELS = frozenset({"roadmap/rfc", "roadmap/epic"})
EXECUTION_STATES = frozenset(
    {"merge-ready", "review", "in-progress", "claimed"}
)
_STATE_PRIORITY_ORDER = (
    "blocked",
    "done",
    "merge-ready",
    "review",
    "in-progress",
    "handoff",
    "claimed",
    "ready",
)

ORCHESTRA_GOVERNED_LABEL = "orchestra-governed"


# ---------------------------------------------------------------------------
# Predicates (pure functions, no I/O)
# ---------------------------------------------------------------------------


def has_roadmap_label(labels: list[str]) -> bool:
    """Whether labels contain roadmap/rfc or roadmap/epic."""
    return bool(_ROADMAP_LABELS & set(labels))


def has_roadmap_conflict(labels: list[str]) -> bool:
    """Whether labels have both a roadmap label and a state/* label."""
    if not has_roadmap_label(labels):
        return False
    return any(lb.startswith("state/") for lb in labels)


def has_execution_state(labels: list[str]) -> bool:
    """Whether labels contain an execution-phase state/* label."""
    return bool(
        EXECUTION_STATES
        & {lb.removeprefix("state/") for lb in labels if lb.startswith("state/")}
    )


def has_orchestra_governed(labels: list[str]) -> bool:
    """Whether labels contain orchestra-governed."""
    return "orchestra-governed" in labels


def get_state_labels(labels: list[str]) -> list[str]:
    """Extract all state/* labels."""
    return [lb for lb in labels if lb.startswith("state/")]


def get_highest_priority_state(labels: list[str]) -> str | None:
    """Return highest-priority state/* label from labels, or None."""
    state_set = set(get_state_labels(labels))
    for priority_state in _STATE_PRIORITY_ORDER:
        candidate = f"state/{priority_state}"
        if candidate in state_set:
            return candidate
    return None


def get_conflicting_states(labels: list[str]) -> list[str]:
    """Return lower-priority state/* labels that should be removed."""
    states = get_state_labels(labels)
    if len(states) <= 1:
        return []
    highest = get_highest_priority_state(labels)
    return [lb for lb in states if lb != highest]


# ---------------------------------------------------------------------------
# Composition layer
# ---------------------------------------------------------------------------


def classify_dispatch_eligibility(
    labels: list[str],
    assignees: list[str],
    *,
    supervisor_label: str,
    manager_usernames: tuple[str, ...],
) -> list["DispatchExclusion"]:
    """Unified dispatch exclusion logic. Single source of truth.

    Returns list of reasons why issue should not be auto-dispatched.
    """
    from vibe3.models import DispatchExclusion

    reasons: list[DispatchExclusion] = []

    state_labels = get_state_labels(labels)
    if not state_labels:
        reasons.append(
            DispatchExclusion("missing_state_label", "missing state/* label")
        )
    elif get_highest_priority_state(labels) == "state/blocked":
        reasons.append(
            DispatchExclusion("blocked_state", "blocked issues require resume")
        )

    if has_roadmap_label(labels):
        for label in _ROADMAP_LABELS:
            if label in labels:
                reasons.append(
                    DispatchExclusion(
                        f"roadmap_{label.split('/')[-1]}",
                        f"roadmap {label.split('/')[-1]}",
                    )
                )

    if supervisor_label in labels:
        reasons.append(DispatchExclusion("supervisor_issue", "supervisor issue"))

    if not has_manager_assignee(assignees, manager_usernames):
        if not assignees:
            reasons.append(
                DispatchExclusion(
                    "missing_manager_assignee", "missing manager assignee"
                )
            )
        else:
            reasons.append(
                DispatchExclusion("non_manager_assignee", "assignee is not manager")
            )

    return reasons


# LabelAnomaly and collect_label_anomalies moved to label_anomalies.py
