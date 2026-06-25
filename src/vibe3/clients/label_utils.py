"""Label normalization and anomaly detection utilities.

These utilities are used by both orchestra (KERNEL) and services (COMMAND_ADAPTER),
so they're placed in clients (not in taxonomy) to avoid category dependency violations.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from vibe3.clients.sync_rules import SyncRulesConfig


def normalize_labels(raw_labels: object) -> list[str]:
    """Extract label names from GitHub issue payload labels field.

    Handles both GitHub API format (list of dicts with "name" key) and
    plain string lists (used in tests or simplified payloads).

    Supported input formats:
      - ``list[dict[str, str]]`` — GitHub API (each dict has a ``"name"`` key)
      - ``list[str]`` — plain string labels
      - Anything else — returns ``[]``

    Mixed lists (containing both dicts and strings) are accepted but not
    recommended; callers should pass a uniform list.
    """
    if not isinstance(raw_labels, list):
        return []
    result: list[str] = []
    for item in raw_labels:
        if isinstance(item, dict):
            name = item.get("name")
            if isinstance(name, str):
                result.append(name)
        elif isinstance(item, str):
            result.append(item)
        else:
            logger.bind(domain="shared/labels").debug(
                "normalize_labels: skipping unexpected item type: {}", type(item)
            )
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


# Label constants duplicated from services/shared/labels.py to avoid
# cross-category imports. Keep these semantics in sync.
ROADMAP_LIFECYCLE_LABELS = frozenset({"roadmap/rfc", "roadmap/epic"})
EXECUTION_STATES = frozenset({"merge-ready", "review", "in-progress", "claimed"})
STATE_PRIORITY_ORDER = (
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


def has_roadmap_label(labels: list[str]) -> bool:
    """Check if issue has an RFC or epic roadmap lifecycle label."""
    return bool(ROADMAP_LIFECYCLE_LABELS & set(labels))


def has_execution_state(labels: list[str]) -> bool:
    """Check if issue has an execution state label."""
    return any(
        lb.startswith("state/") and lb.removeprefix("state/") in EXECUTION_STATES
        for lb in labels
    )


def get_state_labels(labels: list[str]) -> list[str]:
    """Get all state labels from label list."""
    return [lb for lb in labels if lb.startswith("state/")]


def get_highest_priority_state(labels: list[str]) -> str | None:
    """Return highest-priority state/* label from labels, or None."""
    state_set = set(get_state_labels(labels))
    for priority_state in STATE_PRIORITY_ORDER:
        candidate = f"state/{priority_state}"
        if candidate in state_set:
            return candidate
    return None


def has_orchestra_governed(labels: list[str]) -> bool:
    """Check if issue has orchestra-governed label."""
    return ORCHESTRA_GOVERNED_LABEL in labels


def get_conflicting_states(labels: list[str]) -> list[str]:
    """Get conflicting state labels (multiple state labels on same issue)."""
    state_labels = get_state_labels(labels)
    if len(state_labels) <= 1:
        return []
    highest = get_highest_priority_state(labels)
    return [lb for lb in state_labels if lb != highest]


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
    Rules evaluated in priority order; roadmap_conflict suppresses
    multi_state and orphan_execution rules.

    Args:
        labels: List of label strings
        issue_number: GitHub issue number
        has_local_flow: Whether issue has local flow
        is_manager_issue: Whether this is a manager issue
        rules: Sync rules config (None = all rules enabled for backward compatibility)
    """
    removed: list[str] = []
    added: list[str] = []
    rules_found: list[str] = []

    # Rule 1: roadmap + state conflict
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
        # Rule 2: multiple state labels
        if rules is None or rules.remote.multi_state.enabled:
            conflicts = get_conflicting_states(labels)
            if conflicts:
                removed.extend(conflicts)
                rules_found.append("multi_state")

        # Rule 3: orphan execution state (manager issues only)
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

    # Rule 4: governed issue missing its terminal state (manager issues only)
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
