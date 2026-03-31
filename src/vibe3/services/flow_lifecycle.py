"""Flow lifecycle operations - block."""

from typing import Any

from loguru import logger

from vibe3.exceptions import UserError
from vibe3.models.orchestration import IssueState
from vibe3.services.label_service import LabelService
from vibe3.services.signature_service import SignatureService


def sync_flow_blocked_task_label(store: Any, branch: str) -> None:
    """Sync task-role issues in a flow to state/blocked when flow is blocked."""
    issue_links_raw = store.get_issue_links(branch)
    issue_links = issue_links_raw if isinstance(issue_links_raw, list) else []
    label_service = LabelService()
    for link in issue_links:
        if link.get("issue_role") != "task":
            continue
        issue_number = link.get("issue_number")
        if issue_number is None:
            continue
        label_service.confirm_issue_state(
            int(issue_number),
            IssueState.BLOCKED,
            actor="flow:blocked",
            force=True,
        )


class FlowLifecycleMixin:
    """Mixin providing flow lifecycle operations."""

    store: Any
    git_client: Any

    def block_flow(
        self: Any,
        branch: str,
        reason: str | None = None,
        blocked_by_issue: int | None = None,
        actor: str | None = None,
    ) -> None:
        """Mark flow as blocked."""
        logger.bind(
            domain="flow",
            action="block",
            branch=branch,
            reason=reason,
            blocked_by_issue=blocked_by_issue,
        ).info("Blocking flow")

        flow_data = self.store.get_flow_state(branch)
        if not flow_data:
            raise UserError(
                f"当前分支 '{branch}' 没有 flow\n"
                f"先执行 `vibe3 flow add <name>` 或切到已有 flow 的分支"
            )

        effective_actor = SignatureService.resolve_actor(
            explicit_actor=actor,
            flow_actor=flow_data.get("latest_actor"),
        )

        if blocked_by_issue:
            from vibe3.services.task_service import TaskService

            TaskService().link_issue(
                branch,
                blocked_by_issue,
                role="dependency",
                actor=effective_actor,
            )

        blocked_by = reason or (
            f"Blocked by issue #{blocked_by_issue}" if blocked_by_issue else None
        )

        self.store.update_flow_state(
            branch,
            flow_status="blocked",
            blocked_by=blocked_by,
            latest_actor=effective_actor,
        )

        self.store.add_event(
            branch,
            "flow_blocked",
            effective_actor,
            f"Flow blocked{': ' + reason if reason else ''}",
        )
        sync_flow_blocked_task_label(self.store, branch)
