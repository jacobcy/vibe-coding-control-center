"""Label anomaly detection for issue audit.

Extracted from labels.py to keep that module focused on predicates.
"""

from __future__ import annotations

from dataclasses import dataclass

from vibe3.services.shared.labels import (
    EXECUTION_STATES,
    ORCHESTRA_GOVERNED_LABEL,
    get_conflicting_states,
    get_state_labels,
    has_execution_state,
    has_orchestra_governed,
    has_roadmap_label,
)


@dataclass(frozen=True)
class LabelAnomaly:
    """Audit finding for a single issue's label state."""

    issue_number: int
    rule: str  # roadmap_conflict | multi_state | orphan_execution | orphan_orchestra
    removed: list[str]
    added: list[str]


def collect_label_anomalies(
    labels: list[str],
    *,
    issue_number: int,
    has_local_flow: bool,
    is_manager_issue: bool,
) -> list[LabelAnomaly]:
    """Collect all label anomalies for one issue.

    Returns list of anomalies (empty = no issues found).
    Rules evaluated in priority order; roadmap_conflict suppresses
    multi_state and orphan_execution rules.
    """
    removed: list[str] = []
    added: list[str] = []
    rules: list[str] = []

    # Rule 1: roadmap + state conflict
    r1 = (
        [lb for lb in labels if lb.startswith("state/")]
        if has_roadmap_label(labels)
        else []
    )
    if r1:
        removed.extend(r1)
        rules.append("roadmap_conflict")

    if not r1:
        # Rule 2: multiple state labels
        conflicts = get_conflicting_states(labels)
        if conflicts:
            removed.extend(conflicts)
            rules.append("multi_state")

        # Rule 3: orphan execution state (manager issues only)
        if is_manager_issue and not has_local_flow and has_execution_state(labels):
            exec_labels = [
                lb
                for lb in get_state_labels(labels)
                if lb.removeprefix("state/") in EXECUTION_STATES
            ]
            if exec_labels:
                removed.extend(exec_labels)
                added.append("state/ready")
                rules.append("orphan_execution")

    # Rule 4: orphan orchestra-governed (manager issues only)
    if is_manager_issue and has_orchestra_governed(labels):
        has_state = bool(get_state_labels(labels))
        has_roadmap = has_roadmap_label(labels)
        if not has_state and not has_roadmap:
            removed.append(ORCHESTRA_GOVERNED_LABEL)
            rules.append("orphan_orchestra")

    if not rules:
        return []

    # Deduplicate while preserving order
    removed = list(dict.fromkeys(removed))
    added = list(dict.fromkeys(added))

    return [
        LabelAnomaly(
            issue_number=issue_number,
            rule=", ".join(rules),
            removed=removed,
            added=added,
        )
    ]
