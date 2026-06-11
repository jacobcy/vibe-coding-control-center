"""State label recovery predicates for local check."""

from __future__ import annotations

from vibe3.services.shared.labels import get_state_labels, has_roadmap_label


def should_recover_missing_state_label(
    *,
    labels: list[str],
    flow_status: str,
    issue_loaded: bool,
    task_issue_closed: bool,
) -> bool:
    """Whether check may restore a missing state label from local flow refs."""
    return (
        issue_loaded
        and not task_issue_closed
        and flow_status != "blocked"
        and not get_state_labels(labels)
        and not has_roadmap_label(labels)
    )
