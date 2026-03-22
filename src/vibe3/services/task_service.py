"""Task service implementation."""

from typing import TYPE_CHECKING, Literal

from loguru import logger

from vibe3.clients import SQLiteClient
from vibe3.models.flow import FlowState, IssueLink
from vibe3.services.task_bridge_mixin import TaskBridgeMixin

if TYPE_CHECKING:
    from vibe3.clients.github_project_client import GitHubProjectClient


class TaskService(TaskBridgeMixin):
    """Service for managing task state.

    task 状态真源在 GitHub Project，本地 SQLite 只存 flow 执行现场状态。
    bridge 操作（hydrate / update_remote_task_status / link_project_item）
    由 TaskBridgeMixin 提供。
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
        role: Literal["task", "repo"] = "repo",
        actor: str = "unknown",
    ) -> IssueLink:
        """Link an issue to a flow."""
        logger.bind(
            domain="task",
            action="link_issue",
            branch=branch,
            issue_number=issue_number,
            role=role,
            actor=actor,
        ).info("Linking issue to flow")

        self.store.add_issue_link(branch, issue_number, role)

        if role == "task":
            self.store.update_flow_state(
                branch,
                task_issue_number=issue_number,
                latest_actor=actor,
            )

        self.store.add_event(
            branch,
            "issue_linked",
            actor,
            f"Issue #{issue_number} linked as {role}",
        )

        return IssueLink(
            branch=branch,
            issue_number=issue_number,
            issue_role=role,
        )

    def update_flow_status(
        self,
        branch: str,
        status: Literal["active", "blocked", "done", "stale"],
        actor: str = "unknown",
    ) -> FlowState:
        """Update local flow scene status.

        NOTE: flow_status 是本地执行现场状态，不等于 GitHub Project task 状态真源。
        如需更新远端状态，请使用 update_remote_task_status()（来自 TaskBridgeMixin）。
        """
        logger.bind(
            domain="task",
            action="update_flow_status",
            branch=branch,
            status=status,
            actor=actor,
        ).info("Updating local flow scene status")

        flow_data = self.store.get_flow_state(branch)
        if not flow_data:
            raise RuntimeError(f"Flow not found for branch {branch}")

        self.store.update_flow_state(branch, flow_status=status, latest_actor=actor)
        self.store.add_event(
            branch, "status_updated", actor, f"Status changed to {status}"
        )
        return FlowState(**flow_data)
        return FlowState(**flow_data)

    def get_task(self, branch: str) -> FlowState | None:
        """Get task (flow) details."""
        logger.bind(domain="task", action="get", branch=branch).debug("Getting task")
        flow_data = self.store.get_flow_state(branch)
        if not flow_data:
            return None
        return FlowState(**flow_data)

    def set_next_step(
        self,
        branch: str,
        next_step: str,
        actor: str = "unknown",
    ) -> FlowState:
        """Set next step for a task."""
        logger.bind(
            domain="task",
            action="set_next_step",
            branch=branch,
            next_step=next_step,
            actor=actor,
        ).info("Setting next step")

        self.store.update_flow_state(branch, next_step=next_step, latest_actor=actor)
        self.store.add_event(branch, "next_step_set", actor, f"Next step: {next_step}")

        flow_data = self.store.get_flow_state(branch)
        if not flow_data:
            raise RuntimeError(f"Flow not found for branch {branch}")
        return FlowState(**flow_data)
