"""Usecase layer for task command orchestration."""

from dataclasses import dataclass

from vibe3.exceptions import GitError
from vibe3.models.flow import FlowState
from vibe3.models.task_bridge import HydratedTaskView, HydrateError
from vibe3.services.flow_service import FlowService
from vibe3.services.task_service import TaskService


@dataclass
class TaskListRow:
    """UI-friendly task list row."""

    branch: str
    flow_slug: str
    flow_status: str
    task_issue_number: int | None


@dataclass
class TaskShowResult:
    """Task show query result with local and remote context."""

    branch: str
    view: HydratedTaskView | None = None
    hydrate_error: HydrateError | None = None
    local_task: FlowState | None = None
    related_issue_numbers: list[int] | None = None
    dependency_issue_numbers: list[int] | None = None


class TaskUsecase:
    """Coordinate task command behavior with reusable services."""

    def __init__(
        self,
        flow_service: FlowService | None = None,
        task_service: TaskService | None = None,
    ) -> None:
        self.flow_service = flow_service or FlowService()
        self.task_service = task_service or TaskService()

    def list_task_rows(self) -> list[TaskListRow]:
        """List local tasks as UI-oriented rows."""
        task_flows = [
            flow for flow in self.flow_service.list_flows() if flow.task_issue_number
        ]
        rows: list[TaskListRow] = []
        for task_flow in task_flows:
            rows.append(
                TaskListRow(
                    branch=task_flow.branch,
                    flow_slug=task_flow.flow_slug,
                    flow_status=task_flow.flow_status,
                    task_issue_number=task_flow.task_issue_number,
                )
            )
        return rows

    def resolve_branch(self, branch: str | None = None) -> str:
        """Resolve explicit or current branch for task commands."""
        if branch:
            return branch
        try:
            return self.flow_service.get_current_branch()
        except GitError as exc:
            raise RuntimeError(f"unable to resolve current branch ({exc})") from exc

    def show_task(self, branch: str | None = None) -> TaskShowResult:
        """Load task detail with local fallback state."""
        target_branch = self.resolve_branch(branch)
        view = self.task_service.hydrate(target_branch)
        if isinstance(view, HydrateError):
            local_task = self.task_service.get_task(target_branch)
            return TaskShowResult(
                branch=target_branch,
                hydrate_error=view,
                local_task=local_task,
            )

        issue_links = self.flow_service.store.get_issue_links(target_branch)
        related_issue_numbers = [
            link["issue_number"]
            for link in issue_links
            if link["issue_role"] == "related"
        ]
        dependency_issue_numbers = [
            link["issue_number"]
            for link in issue_links
            if link["issue_role"] == "dependency"
        ]
        return TaskShowResult(
            branch=target_branch,
            view=view,
            related_issue_numbers=related_issue_numbers,
            dependency_issue_numbers=dependency_issue_numbers,
        )
