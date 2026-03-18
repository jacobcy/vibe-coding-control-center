"""GitHub client implementation."""

from vibe3.clients.github_client_base import GitHubClientBase
from vibe3.clients.github_issues_ops import IssuesMixin
from vibe3.clients.github_pr_ops import PRMixin
from vibe3.clients.github_review_ops import ReviewMixin
from vibe3.clients.github_status_ops import StatusMixin


class GitHubClient(GitHubClientBase, PRMixin, ReviewMixin, StatusMixin, IssuesMixin):
    """GitHub client for interacting with GitHub via gh CLI.

    This class combines all mixins to provide comprehensive GitHub operations:
    - Base operations (auth check, command execution)
    - PR operations (create, get, update, merge)
    - Review operations (comments, reviews, diff)
    - Status operations (commit status, SHA retrieval)
    - Issues operations (list, view)
    """

    pass
