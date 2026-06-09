"""Label consistency rules for remote label check service."""

from __future__ import annotations

from loguru import logger

# State label priority (highest to lowest)
# Note: This order differs from check_service.py intentionally
# merge-ready is closer to done than review/in-progress
STATE_PRIORITY = [
    "blocked",
    "done",
    "merge-ready",
    "review",
    "in-progress",
    "handoff",
    "claimed",
    "ready",
]

# Execution state labels (for rule 3)
EXECUTION_STATE_LABELS = {
    "state/merge-ready",
    "state/review",
    "state/in-progress",
    "state/handoff",
    "state/claimed",
}


def apply_rule_1(issue_number: int, labels: list[str]) -> tuple[list[str], str] | None:
    """Rule 1: Roadmap label conflict.

    If issue has roadmap/rfc or roadmap/epic, all state/* labels should be removed.

    Returns:
        Tuple of (labels_to_remove, rule_name) or None
    """
    has_roadmap_rfc = "roadmap/rfc" in labels
    has_roadmap_epic = "roadmap/epic" in labels

    if not (has_roadmap_rfc or has_roadmap_epic):
        return None

    # Find all state/* labels
    state_labels = [label for label in labels if label.startswith("state/")]

    if not state_labels:
        return None

    logger.bind(
        issue_number=issue_number,
        roadmap="rfc" if has_roadmap_rfc else "epic",
        state_labels=state_labels,
    ).info("Rule 1: Roadmap label conflict detected")

    return (state_labels, "规则 1 (roadmap 标签冲突)")


def apply_rule_2(issue_number: int, labels: list[str]) -> tuple[list[str], str] | None:
    """Rule 2: Multiple state labels.

    Keep highest priority state, remove others.

    Returns:
        Tuple of (labels_to_remove, rule_name) or None
    """
    state_labels = [label for label in labels if label.startswith("state/")]

    if len(state_labels) <= 1:
        return None

    # Find highest priority state
    highest_priority_state = None
    highest_priority_idx = len(STATE_PRIORITY)

    for state_label in state_labels:
        # Extract state name (e.g., "state/blocked" -> "blocked")
        state_name = state_label.replace("state/", "")

        if state_name in STATE_PRIORITY:
            idx = STATE_PRIORITY.index(state_name)
            if idx < highest_priority_idx:
                highest_priority_idx = idx
                highest_priority_state = state_label

    if highest_priority_state is None:
        # Unknown state labels, skip auto-fix
        logger.bind(
            issue_number=issue_number,
            state_labels=state_labels,
        ).warning("Rule 2: Unknown state labels, skipping auto-fix")
        return None

    # Remove all state labels except the highest priority one
    labels_to_remove = [
        label for label in state_labels if label != highest_priority_state
    ]

    logger.bind(
        issue_number=issue_number,
        keep=highest_priority_state,
        remove=labels_to_remove,
    ).info("Rule 2: Multiple state labels detected")

    return (labels_to_remove, "规则 2 (多个 state 标签)")


def apply_rule_3(
    issue_number: int,
    labels: list[str],
    local_flow_branches: set[str],
) -> tuple[list[str], list[str], str] | None:
    """Rule 3: Orphan execution state labels.

    Manager-assigned issue with execution state but no local flow record.

    Returns:
        Tuple of (labels_to_remove, labels_to_add, rule_name) or None
    """
    # Check if issue has any execution state label
    execution_labels = [label for label in labels if label in EXECUTION_STATE_LABELS]

    if not execution_labels:
        return None

    # Check if canonical branch has local flow record
    canonical_branch = f"task/issue-{issue_number}"

    if canonical_branch in local_flow_branches:
        return None

    # Issue has execution state but no local flow
    logger.bind(
        issue_number=issue_number,
        execution_labels=execution_labels,
        expected_branch=canonical_branch,
    ).info("Rule 3: Orphan execution state detected")

    return (
        execution_labels,
        ["state/ready"],
        "规则 3 (孤儿执行态标签)",
    )


def apply_rule_4(issue_number: int, labels: list[str]) -> tuple[list[str], str] | None:
    """Rule 4: Orphan orchestra-governed.

    Manager-assigned issue with orchestra-governed but no state/* or roadmap labels.

    Returns:
        Tuple of (labels_to_remove, rule_name) or None
    """
    if "orchestra-governed" not in labels:
        return None

    # Check if issue has any state/* label
    has_state_label = any(label.startswith("state/") for label in labels)

    # Check if issue has roadmap labels
    has_roadmap_label = "roadmap/rfc" in labels or "roadmap/epic" in labels

    if has_state_label or has_roadmap_label:
        return None

    # Issue has orchestra-governed but no state/* or roadmap labels
    logger.bind(
        issue_number=issue_number,
    ).info("Rule 4: Orphan orchestra-governed detected")

    return (["orchestra-governed"], "规则 4 (孤儿 orchestra-governed)")
