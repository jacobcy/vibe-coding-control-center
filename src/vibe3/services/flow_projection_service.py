"""Flow projection service combining local and remote data."""

from dataclasses import dataclass
from typing import Any

from loguru import logger

from vibe3.clients import SQLiteClient
from vibe3.clients.github_client import GitHubClient
from vibe3.models.flow import FlowStatusResponse
from vibe3.services.flow_service import FlowService
from vibe3.services.pr_service import PRService
from vibe3.services.task_service import TaskService


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
    ) -> None:
        self.flow_service = flow_service or FlowService()
        self.task_service = task_service or TaskService()
        self.pr_service = pr_service or PRService()
        self.github_client = github_client or GitHubClient()
        self.store = store or SQLiteClient()

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
        """Fetch titles for a list of issues with cache optimization.

        Uses cache-first strategy: checks local cache before calling GitHub API.
        Only calls GitHub for cache misses and updates cache with fetched titles.

        Returns:
            Tuple of (titles_dict, has_network_error)
        """
        titles: dict[int, str] = {}
        network_error = False

        # Group issue numbers by branch to check cache
        # Build mapping: issue_number -> list of branches with this issue as task
        issue_to_branches: dict[int, list[str]] = {}
        for n in issue_numbers:
            # Find branches that have this issue as task_issue_number
            # Note: This requires querying all flows, which may be expensive
            # Alternative: direct cache lookup by constructing branch names
            # For issue-N pattern, likely branches are task/issue-N or dev/issue-N
            possible_branches = [f"task/issue-{n}", f"dev/issue-{n}"]
            issue_to_branches[n] = possible_branches

        # Check cache for each issue
        cache_misses: list[int] = []
        for n in issue_numbers:
            cached_title = None
            # Try each possible branch pattern
            for branch in issue_to_branches[n]:
                cache = self.store.get_flow_context_cache(branch)
                if cache and cache.get("task_issue_number") == n:
                    cached_title = cache.get("issue_title")
                    if cached_title:
                        break  # Found cached title

            if cached_title:
                titles[n] = cached_title
                logger.bind(
                    domain="flow_projection",
                    action="get_issue_titles",
                    issue_number=n,
                    source="cache",
                ).debug(f"Using cached title for issue #{n}")
            else:
                cache_misses.append(n)

        # Fetch missing titles from GitHub
        if cache_misses:
            logger.bind(
                domain="flow_projection",
                action="get_issue_titles",
                cache_misses=cache_misses,
            ).debug(f"Fetching {len(cache_misses)} issues from GitHub")

            for n in cache_misses:
                try:
                    issue = self.github_client.view_issue(n)
                    if isinstance(issue, dict):
                        fetched_title = issue.get("title", f"Issue #{n}")
                        titles[n] = fetched_title

                        # Update cache for all associated branches
                        for branch in issue_to_branches[n]:
                            existing_cache = self.store.get_flow_context_cache(branch)
                            if existing_cache:
                                # Update existing cache entry with title
                                self.store.upsert_flow_context_cache(
                                    branch=branch,
                                    task_issue_number=existing_cache.get(
                                        "task_issue_number"
                                    ),
                                    issue_title=fetched_title,
                                    pr_number=existing_cache.get("pr_number"),
                                    pr_title=existing_cache.get("pr_title"),
                                )
                                logger.bind(
                                    domain="flow_projection",
                                    action="get_issue_titles",
                                    issue_number=n,
                                    branch=branch,
                                ).debug("Updated cache with fetched title")

                    elif issue == "network_error":
                        network_error = True
                except Exception as e:
                    network_error = True
                    logger.bind(
                        domain="flow_projection",
                        action="get_issue_titles",
                        issue_number=n,
                        error=str(e),
                    ).warning(f"Failed to fetch issue #{n} from GitHub")

        return titles, network_error

    def get_milestone_data(self, issue_number: int) -> dict[str, Any] | None:
        """Get milestone data for an issue."""
        try:
            issue = self.github_client.view_issue(issue_number)
            if isinstance(issue, dict):
                milestone = issue.get("milestone")
                if milestone and isinstance(milestone, dict):
                    m_number = milestone.get("number")
                    if m_number:
                        all_issues = self.github_client.get_milestone_issues(m_number)
                        open_issues = [
                            i for i in all_issues if i.get("state") == "open"
                        ]
                        closed_issues = [
                            i for i in all_issues if i.get("state") == "closed"
                        ]
                        return {
                            "title": milestone.get("title"),
                            "number": m_number,
                            "state": milestone.get("state"),
                            "open": len(open_issues),
                            "closed": len(closed_issues),
                            "issues": all_issues,
                            "task_issue": issue,
                        }
        except Exception:
            pass
        return None
