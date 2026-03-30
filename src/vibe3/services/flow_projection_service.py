"""Flow projection service - unified local + remote data reading layer."""

from dataclasses import dataclass
from typing import Any

from vibe3.clients.github_client import GitHubClient
from vibe3.models.task_bridge import HydrateError
from vibe3.services.flow_service import FlowService
from vibe3.services.pr_service import PRService
from vibe3.services.task_service import TaskService


@dataclass
class FlowProjection:
    """Unified flow projection combining local state and remote facts."""

    # Local flow state (runtime only)
    branch: str
    flow_slug: str
    flow_status: str
    spec_ref: str | None = None
    plan_ref: str | None = None
    report_ref: str | None = None
    audit_ref: str | None = None
    planner_actor: str | None = None
    planner_session_id: str | None = None
    executor_actor: str | None = None
    executor_session_id: str | None = None
    reviewer_actor: str | None = None
    reviewer_session_id: str | None = None
    latest_actor: str | None = None
    blocked_by: str | None = None
    next_step: str | None = None
    planner_status: str | None = None
    executor_status: str | None = None
    reviewer_status: str | None = None
    execution_pid: int | None = None
    execution_started_at: str | None = None
    execution_completed_at: str | None = None

    # Remote task facts (from GitHub Project)
    task_issue_number: int | None = None
    project_item_id: str | None = None
    title: str | None = None
    body: str | None = None
    status: str | None = None
    priority: str | None = None
    assignees: list[str] | None = None
    offline_mode: bool = False
    identity_drift: bool = False

    # Remote PR facts (from GitHub API)
    pr_number: int | None = None
    pr_title: str | None = None
    pr_state: str | None = None
    pr_draft: bool | None = None
    pr_url: str | None = None
    pr_ready_for_review: bool | None = None

    # Error states
    hydrate_error: HydrateError | None = None
    pr_fetch_error: bool = False


class FlowProjectionService:
    """Unified projection service for reading flow data with remote facts."""

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

        projection = FlowProjection(
            branch=flow_status.branch,
            flow_slug=flow_status.flow_slug,
            flow_status=flow_status.flow_status,
            task_issue_number=flow_status.task_issue_number,
            pr_number=flow_status.pr_number,
            pr_ready_for_review=flow_status.pr_ready_for_review,
            spec_ref=flow_status.spec_ref,
            plan_ref=flow_status.plan_ref,
            report_ref=flow_status.report_ref,
            audit_ref=flow_status.audit_ref,
            planner_actor=flow_status.planner_actor,
            planner_session_id=flow_status.planner_session_id,
            executor_actor=flow_status.executor_actor,
            executor_session_id=flow_status.executor_session_id,
            reviewer_actor=flow_status.reviewer_actor,
            reviewer_session_id=flow_status.reviewer_session_id,
            latest_actor=flow_status.latest_actor,
            blocked_by=flow_status.blocked_by,
            next_step=flow_status.next_step,
            planner_status=flow_status.planner_status,
            executor_status=flow_status.executor_status,
            reviewer_status=flow_status.reviewer_status,
            execution_pid=flow_status.execution_pid,
            execution_started_at=flow_status.execution_started_at,
            execution_completed_at=flow_status.execution_completed_at,
        )

        if not include_remote:
            return projection

        # Hydrate task data from GitHub Project
        try:
            task_view = self.task_service.hydrate(branch)
            if isinstance(task_view, HydrateError):
                projection.hydrate_error = task_view
            else:
                projection.project_item_id = (
                    task_view.project_item_id.value
                    if task_view.project_item_id
                    else None
                )
                projection.title = task_view.title.value if task_view.title else None
                projection.body = task_view.body.value if task_view.body else None
                projection.status = task_view.status.value if task_view.status else None
                projection.priority = (
                    task_view.priority.value if task_view.priority else None
                )
                projection.assignees = (
                    task_view.assignees.value if task_view.assignees else None
                )
                projection.offline_mode = task_view.offline_mode
                projection.identity_drift = task_view.identity_drift
        except Exception as e:
            projection.hydrate_error = HydrateError(
                type="hydrate_failed", message=f"Failed to hydrate task data: {str(e)}"
            )

        # Fetch PR data from GitHub
        try:
            pr = self.pr_service.get_pr(branch=branch)
            if pr:
                projection.pr_number = pr.number
                projection.pr_title = pr.title
                projection.pr_state = pr.state.value
                projection.pr_draft = pr.draft
                projection.pr_url = pr.url
                projection.pr_ready_for_review = not pr.draft
        except Exception:
            projection.pr_fetch_error = True

        return projection

    def get_issue_titles(self, issue_numbers: list[int]) -> tuple[dict[int, str], bool]:
        """Fetch issue titles from GitHub, with network error flag."""
        titles: dict[int, str] = {}
        network_error = False

        for number in issue_numbers:
            try:
                result = self.github_client.view_issue(number)
                if result == "network_error":
                    network_error = True
                    break
                if isinstance(result, dict):
                    titles[number] = result.get("title", "")
            except Exception:
                network_error = True
                break

        return titles, network_error

    def get_milestone_data(self, issue_number: int) -> dict[str, Any] | None:
        """Fetch milestone data for an issue from GitHub."""
        try:
            issue = self.github_client.view_issue(issue_number)
            if not isinstance(issue, dict) or not issue.get("milestone"):
                return None

            ms = issue["milestone"]
            ms_issues = self.github_client.get_milestone_issues(ms["number"])
            open_count = sum(
                1 for i in ms_issues if str(i.get("state", "")).upper() == "OPEN"
            )
            closed_count = sum(
                1 for i in ms_issues if str(i.get("state", "")).upper() == "CLOSED"
            )

            return {
                "number": ms["number"],
                "title": ms["title"],
                "open": open_count,
                "closed": closed_count,
                "issues": ms_issues,
                "task_issue": issue_number,
            }
        except Exception:
            return None
