"""Label utility functions."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vibe3.models.orchestration import IssueInfo


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


def should_skip_from_queue(
    issue: IssueInfo,
    *,
    supervisor_label: str,
    manager_usernames: list[str] | tuple[str, ...],
) -> bool:
    """Check whether an issue should be skipped from dispatch queue.

    Issues are skipped if:
    1. They have the supervisor label (managed by supervisor, not auto-dispatch)
    2. They don't have a manager assignee (when managers are configured)

    Args:
        issue: Issue information
        supervisor_label: Label name for supervisor issues (from config)
        manager_usernames: List of manager usernames (from config)

    Returns:
        True if issue should be skipped, False otherwise
    """
    # Skip supervisor-managed issues
    if supervisor_label in issue.labels:
        return True

    # Skip issues without manager assignee
    if not has_manager_assignee(issue.assignees, manager_usernames):
        return True

    return False
