"""GitHub API field constants for efficient data fetching.

These constants define commonly used field sets for GitHub issue API calls
to eliminate over-fetching and improve performance.
"""

from typing import Final

# =============================================================================
# GitHub Issue Field Constants
# =============================================================================

# Default fields for view_issue - excludes expensive 'comments' field
# Suitable for callers that need issue metadata but not comments
GITHUB_DEFAULT_VIEW_FIELDS: Final[tuple[str, ...]] = (
    "number",
    "title",
    "body",
    "state",
    "updatedAt",
    "labels",
    "milestone",
    "assignees",
)

# Minimal field sets for specific operations
GITHUB_FIELDS_STATE_ONLY: Final[tuple[str, ...]] = ("state",)
GITHUB_FIELDS_TITLE_ONLY: Final[tuple[str, ...]] = ("title",)

# Fields for operations that need body and comments
GITHUB_FIELDS_BODY_COMMENTS: Final[tuple[str, ...]] = ("body", "comments")

# Complete set of all valid GitHub Issue API fields (for validation)
# Sourced from `gh issue view --help` and `gh issue list --help` JSON FIELDS sections
GITHUB_KNOWN_ISSUE_FIELDS: Final[tuple[str, ...]] = (
    "assignees",
    "author",
    "body",
    "closed",
    "closedAt",
    "closedByPullRequestsReferences",
    "comments",
    "createdAt",
    "id",
    "isPinned",
    "labels",
    "milestone",
    "number",
    "projectCards",
    "projectItems",
    "reactionGroups",
    "state",
    "stateReason",
    "title",
    "updatedAt",
    "url",
)
