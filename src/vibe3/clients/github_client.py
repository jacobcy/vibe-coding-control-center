"""GitHub client implementation."""

import functools

from vibe3.clients.github_client_base import GitHubClientBase
from vibe3.clients.github_comment_ops import CommentMixin
from vibe3.clients.github_issue_admin_ops import IssueAdminMixin
from vibe3.clients.github_issues_ops import IssuesMixin
from vibe3.clients.github_pr_ops import PRMixin
from vibe3.clients.github_review_ops import ReviewMixin


class GitHubClient(
    GitHubClientBase,
    PRMixin,
    ReviewMixin,
    IssuesMixin,
    CommentMixin,
    IssueAdminMixin,
):
    """GitHub client for interacting with GitHub via gh CLI.

    This class combines all mixins to provide comprehensive GitHub operations:
    - Base operations (auth check, command execution)
    - PR operations (create, get, update, merge, query)
    - Review operations (comments, reviews, diff)
    - Issues operations (list, view)
    - Issue admin operations (close, add comment)
    """

    pass


# ── Factory Functions for Process-Level Caching ─────────────────────────────


@functools.lru_cache(maxsize=1)
def get_github_client() -> GitHubClient:
    """Get a cached GitHubClient singleton for the current process.

    This factory eliminates redundant GitHubClient instantiations during a single
    CLI invocation, reducing subprocess overhead. The cache is process-local
    and thread-safe.

    Returns:
        Cached GitHubClient instance

    Example:
        >>> client1 = get_github_client()
        >>> client2 = get_github_client()
        >>> assert client1 is client2  # Same instance
    """
    return GitHubClient()


def clear_github_client_cache() -> None:
    """Clear the GitHubClient singleton cache.

    This should be called in test fixtures to ensure test isolation.
    """
    get_github_client.cache_clear()
