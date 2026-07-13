"""GitHub API field constants for efficient data fetching.

These constants define commonly used field sets for GitHub issue API calls
to eliminate over-fetching and improve performance.
"""

from typing import Final

# =============================================================================
# GitHub Issue Field Constants
# =============================================================================

# Default fields for view_issue — includes body and url
GITHUB_DEFAULT_VIEW_FIELDS: Final[tuple[str, ...]] = (
    "number",
    "title",
    "state",
    "updatedAt",
    "labels",
    "assignees",
    "milestone",
    "body",
    "url",
)

# Default fields for list_issues — excludes body (expensive) and url
GITHUB_DEFAULT_LIST_FIELDS: Final[tuple[str, ...]] = (
    "number",
    "title",
    "state",
    "updatedAt",
    "labels",
    "assignees",
    "milestone",
)


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

# =============================================================================
# Issue Field Subsets for Specific Operations
# =============================================================================

# For batch_get_issues — only need number and title
GITHUB_FIELDS_ISSUE_NUMBER_TITLE: Final[tuple[str, ...]] = ("number", "title")

# For get_issue_body — single field
GITHUB_FIELDS_BODY: Final[tuple[str, ...]] = ("body",)

# For get_issue_snapshot — body + updatedAt (optimistic lock for auto resume)
GITHUB_FIELDS_BODY_UPDATED_AT: Final[tuple[str, ...]] = ("body", "updatedAt")

# For list_issue_comments — single field
GITHUB_FIELDS_COMMENTS: Final[tuple[str, ...]] = ("comments",)

# =============================================================================
# GitHub PR Field Constants
# =============================================================================

# Fields for list_merged_prs
GITHUB_PR_LIST_MERGED_FIELDS: Final[tuple[str, ...]] = (
    "number",
    "headRefName",
    "body",
    "mergedAt",
)

# Complete set of all valid GitHub PR API fields (for validation)
# Sourced from `gh pr list --help` JSON FIELDS section
GITHUB_KNOWN_PR_FIELDS: Final[tuple[str, ...]] = (
    "additions",
    "assignees",
    "author",
    "autoMergeRequest",
    "baseRefName",
    "baseRefOid",
    "body",
    "changedFiles",
    "closed",
    "closedAt",
    "closingIssuesReferences",
    "comments",
    "commits",
    "createdAt",
    "deletions",
    "files",
    "fullDatabaseId",
    "headRefName",
    "headRefOid",
    "headRepository",
    "headRepositoryOwner",
    "id",
    "isCrossRepository",
    "isDraft",
    "labels",
    "latestReviews",
    "maintainerCanModify",
    "mergeCommit",
    "mergeStateStatus",
    "mergeable",
    "mergedAt",
    "mergedBy",
    "milestone",
    "number",
    "potentialMergeCommit",
    "projectCards",
    "projectItems",
    "reactionGroups",
    "reviewDecision",
    "reviewRequests",
    "reviews",
    "state",
    "statusCheckRollup",
    "title",
    "updatedAt",
    "url",
)
