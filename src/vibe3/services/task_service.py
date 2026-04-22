"""Task service implementation."""

from dataclasses import dataclass
from typing import Literal

from loguru import logger

from vibe3.clients import SQLiteClient
from vibe3.clients.github_client import GitHubClient
from vibe3.exceptions import GitError
from vibe3.models.flow import FlowStatusResponse, IssueLink
from vibe3.services.flow_service import FlowService
from vibe3.services.signature_service import SignatureService
from vibe3.utils.issue_branch_resolver import resolve_issue_branch_input


@dataclass
class TaskListRow:
    """UI-friendly task list row."""

    branch: str
    flow_slug: str
    flow_status: str
    task_issue_number: int | None


@dataclass
class TaskShowResult:
    """Task show query result with local context."""

    branch: str
    local_task: FlowStatusResponse | None = None
    related_issue_numbers: list[int] | None = None
    dependency_issue_numbers: list[int] | None = None


class TaskService:
    """Service for managing task state."""

    def __init__(
        self,
        store: SQLiteClient | None = None,
    ) -> None:
        self.store = SQLiteClient() if store is None else store
        self._flow_service = FlowService(store=self.store)

    # ------------------------------------------------------------------
    # Core task operations
    # ------------------------------------------------------------------

    def link_issue(
        self,
        branch: str,
        issue_number: int,
        role: Literal["task", "related", "dependency"] = "related",
        actor: str | None = None,
    ) -> IssueLink:
        """Link an issue to a flow."""
        logger.bind(
            domain="task",
            action="link_issue",
            branch=branch,
            issue_number=issue_number,
            role=role,
        ).info("Linking issue to flow")

        effective_actor = SignatureService.resolve_for_branch(
            self.store,
            branch,
            explicit_actor=actor,
        )

        self.store.add_issue_link(branch, issue_number, role)

        if role == "task":
            # task_issue_number is no longer stored in flow_state.
            # We only update latest_actor to track activity.
            self.store.update_flow_state(
                branch,
                latest_actor=effective_actor,
            )

        self.store.add_event(
            branch,
            "issue_linked",
            effective_actor,
            f"Issue #{issue_number} linked as {role}",
        )

        return IssueLink(
            branch=branch,
            issue_number=issue_number,
            issue_role=role,
        )

    def reclassify_issue(
        self,
        branch: str,
        issue_number: int,
        *,
        old_role: Literal["task", "related", "dependency"],
        new_role: Literal["task", "related", "dependency"],
        actor: str | None = None,
    ) -> IssueLink:
        """Reclassify an existing issue link without deleting flow history."""
        logger.bind(
            domain="task",
            action="reclassify_issue",
            branch=branch,
            issue_number=issue_number,
            old_role=old_role,
            new_role=new_role,
        ).info("Reclassifying issue link")

        effective_actor = SignatureService.resolve_for_branch(
            self.store,
            branch,
            explicit_actor=actor,
        )

        updated = self.store.update_issue_link_role(
            branch,
            issue_number,
            old_role,
            new_role,
        )
        if not updated:
            raise ValueError(
                f"Issue #{issue_number} not linked as {old_role} on flow {branch}"
            )

        self.store.update_flow_state(
            branch,
            latest_actor=effective_actor,
        )
        self.store.add_event(
            branch,
            "issue_reclassified",
            effective_actor,
            f"Issue #{issue_number} reclassified: {old_role} -> {new_role}",
        )

        return IssueLink(
            branch=branch,
            issue_number=issue_number,
            issue_role=new_role,
        )

    def get_task(self, branch: str) -> FlowStatusResponse | None:
        """Get task (flow) details."""
        logger.bind(domain="task", action="get", branch=branch).debug("Getting task")
        return self._flow_service.get_flow_status(branch)

    def fetch_issue_with_comments(
        self, issue_number: int
    ) -> dict[str, object] | str | None:
        """Fetch issue data including comments from GitHub.

        Args:
            issue_number: GitHub issue number

        Returns:
            Issue dict, "network_error" string, or None if not found
        """
        return GitHubClient().view_issue(issue_number)

    # ------------------------------------------------------------------
    # Task query operations (merged from task_usecase.py)
    # ------------------------------------------------------------------

    def list_task_rows(self) -> list[TaskListRow]:
        """List local tasks as UI-oriented rows."""
        task_flows = [
            flow for flow in self._flow_service.list_flows() if flow.task_issue_number
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
            return resolve_issue_branch_input(branch, self._flow_service) or branch
        try:
            return self._flow_service.get_current_branch()
        except GitError as exc:
            raise RuntimeError(f"unable to resolve current branch ({exc})") from exc

    def show_task(self, branch: str | None = None) -> TaskShowResult:
        """Load task detail from local state."""
        target_branch = self.resolve_branch(branch)
        local_task = self.get_task(target_branch)

        issue_links = self.store.get_issue_links(target_branch)
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
            local_task=local_task,
            related_issue_numbers=related_issue_numbers,
            dependency_issue_numbers=dependency_issue_numbers,
        )
