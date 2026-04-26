"""Flow projection service combining local and remote data."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from vibe3.clients import SQLiteClient
from vibe3.clients.github_client import GitHubClient
from vibe3.models.flow import FlowStatusResponse
from vibe3.services.flow_service import FlowService
from vibe3.services.pr_service import PRService
from vibe3.services.task_service import TaskService

if TYPE_CHECKING:
    from vibe3.services.issue_title_cache_service import IssueTitleCacheService


@dataclass
class FlowProjection:
    """Unified view of a flow with local and remote data."""

    branch: str
    flow_slug: str
    flow_status: str
    task_issue_number: int | None = None
    spec_ref: str | None = None
    next_step: str | None = None
    blocked_by: str | None = None

    # GitHub PR data
    pr_number: int | None = None
    pr_status: str | None = None
    pr_is_draft: bool = False
    pr_url: str | None = None
    pr_fetch_error: Any | None = None

    # Error flags
    hydrate_error: Any | None = None
    offline_mode: bool = False

    @classmethod
    def from_flow_status(cls, status: FlowStatusResponse) -> "FlowProjection":
        """Create projection from basic flow status."""
        return cls(
            branch=status.branch,
            flow_slug=status.flow_slug,
            flow_status=status.flow_status,
            task_issue_number=status.task_issue_number,
            pr_number=status.pr_number,
            spec_ref=status.spec_ref,
            next_step=status.next_step,
            blocked_by=status.blocked_by,
        )


class FlowProjectionService:
    """Service for building unified flow projections."""

    def __init__(
        self,
        flow_service: FlowService | None = None,
        task_service: TaskService | None = None,
        pr_service: PRService | None = None,
        github_client: GitHubClient | None = None,
        store: SQLiteClient | None = None,
        title_cache: IssueTitleCacheService | None = None,
    ) -> None:
        self.flow_service = flow_service or FlowService()
        self.task_service = task_service or TaskService()
        self.pr_service = pr_service or PRService()
        self.github_client = github_client or GitHubClient()
        self.store = store or SQLiteClient()
        self._title_cache = title_cache

    @property
    def title_cache(self) -> IssueTitleCacheService:
        """Lazy-initialized title cache service."""
        if self._title_cache is None:
            from vibe3.services.issue_title_cache_service import IssueTitleCacheService

            self._title_cache = IssueTitleCacheService(self.store, self.github_client)
        return self._title_cache

    def get_projection(
        self, branch: str, include_remote: bool = True
    ) -> FlowProjection:
        """Get unified flow projection combining local and remote data."""
        # Get local flow state first
        flow_status = self.flow_service.get_flow_status(branch)
        if not flow_status:
            raise ValueError(f"Flow not found for branch: {branch}")

        projection = FlowProjection.from_flow_status(flow_status)

        if not include_remote:
            return projection

        # Get PR data
        try:
            prs = self.pr_service.github_client.list_prs_for_branch(branch)
            if prs:
                pr = prs[0]
                projection.pr_number = pr.number
                projection.pr_status = pr.state.value
                projection.pr_is_draft = pr.draft
                projection.pr_url = pr.url
        except Exception as e:
            projection.pr_fetch_error = str(e)

        return projection

    def get_issue_titles(self, issue_numbers: list[int]) -> tuple[dict[int, str], bool]:
        """Fetch titles for a list of issues.

        NOTE: This method is used by commands, but we need to convert issue_numbers
        to branches first using IssueFlowService.

        Returns:
            Tuple of (issue_number -> title dict, had_network_error)
        """
        from vibe3.services.issue_flow_service import IssueFlowService

        issue_flow = IssueFlowService(self.store)

        # Convert issue_numbers to branches
        # Priority: use actual flow branch (could be dev/issue-N) over canonical guess
        issue_to_branch: dict[int, str] = {}
        branches: list[str] = []
        for n in issue_numbers:
            # Try to find actual flow branch first
            flow_state = issue_flow.find_active_flow(n)
            if flow_state and flow_state.get("branch"):
                branch = str(flow_state["branch"])
            else:
                # Fallback to canonical branch name
                branch = issue_flow.canonical_branch_name(n)

            issue_to_branch[n] = branch
            branches.append(branch)

        # Get titles using cache service (branch-based)
        branch_titles, net_err = self.title_cache.get_titles_with_fallback(branches)

        # Convert back to issue_number -> title mapping
        issue_titles: dict[int, str] = {}
        for n, branch in issue_to_branch.items():
            if branch in branch_titles:
                issue_titles[n] = branch_titles[branch]

        return issue_titles, net_err
