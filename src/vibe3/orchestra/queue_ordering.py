"""Queue ordering utilities for orchestra ready queue."""

from __future__ import annotations

import re
from typing import Any

from vibe3.models.orchestration import IssueInfo

# Legacy priority label mapping to numeric priority
LEGACY_PRIORITY_MAP: dict[str, int] = {
    "critical": 9,
    "high": 7,
    "medium": 5,
    "low": 3,
}


def resolve_priority(labels: list[str]) -> int:
    """Resolve priority from labels.

    Priority is determined by:
    1. Numeric priority labels (priority/[0-9])
    2. Legacy priority labels (priority/critical|high|medium|low)
    3. Fallback to 0 if no priority label found

    When multiple priority labels exist, highest wins.

    Args:
        labels: List of GitHub issue labels

    Returns:
        Numeric priority (0-9)
    """
    priorities: list[int] = []

    for label in labels:
        if label.startswith("priority/"):
            suffix = label[9:]

            # Check for numeric priority
            if re.match(r"^\d+$", suffix):
                priorities.append(int(suffix))

            # Check for legacy priority
            elif suffix in LEGACY_PRIORITY_MAP:
                priorities.append(LEGACY_PRIORITY_MAP[suffix])

    # Return highest priority, or fallback to 0
    return max(priorities) if priorities else 0


def resolve_roadmap_rank(labels: list[str]) -> tuple[int, str | None]:
    """Resolve roadmap rank from labels.

    Roadmap rank is used for milestone-internal ordering.

    Args:
        labels: List of GitHub issue labels

    Returns:
        Tuple of (rank, roadmap_name)
        - rank: Sortable integer rank (0-10 for roadmap labels, >10 for missing)
        - roadmap_name: Roadmap label name (e.g., "p0", "p1") or None
    """
    for label in labels:
        if label.startswith("roadmap/"):
            suffix = label[8:]

            # Parse roadmap/p0, roadmap/p1, etc.
            if re.match(r"^p\d+$", suffix):
                rank = int(suffix[1:])
                return (rank, suffix)

    # Missing roadmap gets high fallback rank (sorts after roadmap-labeled)
    return (100, None)


def resolve_milestone_rank(milestone: dict[str, Any] | None) -> tuple[int, str]:
    """Resolve milestone rank from milestone metadata.

    Milestone is the primary sort bucket (large bucket).

    Args:
        milestone: Milestone dict with 'title' and 'number' fields, or None

    Returns:
        Tuple of (rank, milestone_title)
        - rank: Sortable integer rank
        - milestone_title: Milestone title or empty string
    """
    if milestone is None:
        # Missing milestone gets high fallback rank (sorts after milestone-labeled)
        return (10000, "")

    title = milestone.get("title", "")
    number = milestone.get("number", 0)

    # Parse version milestone (v0.1, v0.3, etc.)
    if re.match(r"^v\d+\.\d+$", title):
        # Extract version number (e.g., v0.1 -> 0.01, v0.3 -> 0.03)
        parts = title[1:].split(".")
        if len(parts) == 2:
            major, minor = int(parts[0]), int(parts[1])
            # Create sortable rank: v0.1 = 100, v0.3 = 300, etc.
            rank = major * 1000 + minor * 100
            return (rank, title)

    # Fallback: use milestone number as rank
    return (number, title)


def sort_ready_issues(issues: list[IssueInfo]) -> list[IssueInfo]:
    """Sort ready queue issues by queue ordering rules.

    Sort order (primary to secondary):
    1. Milestone (large bucket)
    2. Roadmap rank (milestone-internal ordering)
    3. Priority (numeric 0-9, higher is more urgent)

    Args:
        issues: List of IssueInfo objects with ready state

    Returns:
        Sorted list of IssueInfo objects
    """
    # Parse milestone from labels for each issue
    # (Simplified approach; real implementation may get milestone from GitHub API)

    def get_sort_key(issue: IssueInfo) -> tuple[int, int, int]:
        """Compute sort key for an issue: (milestone_rank, roadmap_rank, priority)."""
        # Use IssueInfo.milestone (from GitHub milestone field)
        milestone_dict: dict[str, Any] | None = None
        if issue.milestone:
            milestone_dict = {"title": issue.milestone, "number": 0}

        milestone_rank, _ = resolve_milestone_rank(milestone_dict)
        roadmap_rank, _ = resolve_roadmap_rank(issue.labels)
        priority = resolve_priority(issue.labels)

        # Sort order:
        # - Milestone: lower version number (v0.1) comes first (ascending order)
        # - Roadmap: lower rank (p0) comes first (ascending order)
        # - Priority: higher priority (9) comes first (negate for descending)
        return (milestone_rank, roadmap_rank, -priority)

    # Sort by key
    return sorted(issues, key=get_sort_key)
