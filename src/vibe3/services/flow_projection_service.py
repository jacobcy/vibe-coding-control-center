"""Flow projection service combining local and remote data."""

from dataclasses import dataclass
from typing import Any

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
    ) -> None:
        self.flow_service = flow_service or FlowService()
        self.task_service = task_service or TaskService()
        self.pr_service = pr_service or PRService()
        self.github_client = github_client or GitHubClient()

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

        Returns:
            Tuple of (titles_dict, has_network_error)
        """
        titles: dict[int, str] = {}
        network_error = False
        for n in issue_numbers:
            try:
                issue = self.github_client.view_issue(n)
                if isinstance(issue, dict):
                    titles[n] = issue.get("title", f"Issue #{n}")
                elif issue == "network_error":
                    network_error = True
            except Exception:
                network_error = True
        return titles, network_error

    def get_milestone_data(self, issue_number: int) -> dict[str, Any] | None:
        """Get milestone data for an issue."""
        try:
            issue = self.github_client.view_issue(issue_number)
            if isinstance(issue, dict):
                milestone = issue.get("milestone")
                if milestone and isinstance(milestone, dict):
                    return {
                        "title": milestone.get("title"),
                        "number": milestone.get("number"),
                        "state": milestone.get("state"),
                    }
        except Exception:
            pass
        return None
