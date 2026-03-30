"""Task service implementation."""

from typing import TYPE_CHECKING, Literal

from loguru import logger

from vibe3.clients import SQLiteClient
from vibe3.models.flow import FlowStatusResponse, IssueLink
from vibe3.models.project_item import LinkError
from vibe3.services.flow_query_mixin import FlowQueryMixin
from vibe3.services.signature_service import SignatureService
from vibe3.services.task_bridge_mixin import TaskBridgeMixin

if TYPE_CHECKING:
    from vibe3.clients.github_project_client import GitHubProjectClient


class TaskService(TaskBridgeMixin, FlowQueryMixin):
    """Service for managing task state.

    task 状态真源在 GitHub Project，本地 SQLite 只存 flow 执行现场状态。
    bridge 操作（hydrate / auto_link_issue_to_project）由 TaskBridgeMixin 提供。
    """

    def __init__(
        self,
        store: SQLiteClient | None = None,
        project_client: "GitHubProjectClient | None" = None,
    ) -> None:
        self.store = store or SQLiteClient()
        self._project_client: "GitHubProjectClient | None" = project_client

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

        if role in {"task", "dependency"}:
            link_result = self.auto_link_issue_to_project(branch, issue_number)
            if isinstance(link_result, LinkError):
                logger.bind(
                    domain="task",
                    action="link_issue",
                    branch=branch,
                    issue_number=issue_number,
                    role=role,
                ).warning(f"Auto project link skipped: {link_result.message}")

        return IssueLink(
            branch=branch,
            issue_number=issue_number,
            issue_role=role,
        )

    def get_task(self, branch: str) -> FlowStatusResponse | None:
        """Get task (flow) details."""
        logger.bind(domain="task", action="get", branch=branch).debug("Getting task")
        return self.get_flow_status(branch)
