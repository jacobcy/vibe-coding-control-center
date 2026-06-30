"""Label anomaly detection utilities.

Implements the four label-normalization rules used by the sync/check flow:
``roadmap_conflict``, ``multi_state``, ``orphan_execution``,
``governed_missing_state``. See #3208 for the supervisor-label exception.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vibe3.clients import SyncRulesConfig


# Supervisor issues manage their own state labels (e.g. state/handoff) and must
# not have them stripped by normalization. See #3208.
SUPERVISOR_LABEL = "supervisor"


def has_supervisor_label(labels: list[str]) -> bool:
    """Check if issue has the supervisor label."""
    return SUPERVISOR_LABEL in labels


@dataclass(frozen=True)
class LabelAnomaly:
    """Audit finding for a single issue's label state."""

    issue_number: int
    # roadmap_conflict | multi_state | orphan_execution | governed_missing_state
    rule: str
    removed: list[str]
    added: list[str]


def collect_label_anomalies(
    labels: list[str],
    *,
    issue_number: int,
    has_local_flow: bool,
    is_manager_issue: bool,
    rules: SyncRulesConfig | None = None,
) -> list[LabelAnomaly]:
    """Collect all label anomalies for one issue.

    Returns list of anomalies (empty = no issues found).
    Rules evaluated in priority order; roadmap_conflict suppresses multi_state
    and orphan_execution rules. Supervisor-labeled issues skip the multi_state
    rule — they independently manage their own state labels (e.g. state/handoff).
    """
    from vibe3.services.shared.labels import (  # single source of truth
        EXECUTION_STATES,
        get_conflicting_states,
        get_state_labels,
        has_execution_state,
        has_orchestra_governed,
        has_roadmap_label,
    )

    removed: list[str] = []
    added: list[str] = []
    rules_found: list[str] = []

    if rules is None or rules.remote.roadmap_conflict.enabled:
        r1 = (
            [lb for lb in labels if lb.startswith("state/")]
            if has_roadmap_label(labels)
            else []
        )
        if r1:
            removed.extend(r1)
            rules_found.append("roadmap_conflict")

    if "roadmap_conflict" not in rules_found:
        multi_state_enabled = rules is None or rules.remote.multi_state.enabled
        if multi_state_enabled and not has_supervisor_label(labels):
            conflicts = get_conflicting_states(labels)
            if conflicts:
                removed.extend(conflicts)
                rules_found.append("multi_state")

        if rules is None or rules.remote.orphan_execution.enabled:
            if is_manager_issue and not has_local_flow and has_execution_state(labels):
                exec_labels = [
                    lb
                    for lb in get_state_labels(labels)
                    if lb.removeprefix("state/") in EXECUTION_STATES
                ]
                if exec_labels:
                    removed.extend(exec_labels)
                    added.append("state/ready")
                    rules_found.append("orphan_execution")

    if rules is None or rules.remote.governed_missing_state.enabled:
        if is_manager_issue and has_orchestra_governed(labels):
            has_state = bool(get_state_labels(labels))
            has_roadmap = has_roadmap_label(labels)
            if not has_state and not has_roadmap:
                added.append("state/ready")
                rules_found.append("governed_missing_state")

    if not rules_found:
        return []

    # Deduplicate while preserving order
    removed = list(dict.fromkeys(removed))
    added = list(dict.fromkeys(added))

    return [
        LabelAnomaly(
            issue_number=issue_number,
            rule=", ".join(rules_found),
            removed=removed,
            added=added,
        )
    ]
