"""GitHub client implementation."""

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
