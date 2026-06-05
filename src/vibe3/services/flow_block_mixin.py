"""Flow block/abort operations mixin."""

from typing import Self

from loguru import logger

from vibe3.clients import SQLiteClient
from vibe3.exceptions import UserError
from vibe3.services.shared.signatures import SignatureService


class FlowLifecycleMixin:
    """Mixin providing flow lifecycle operations."""

    store: SQLiteClient

    def block_flow(
        self: Self,
        branch: str,
        reason: str | None = None,
        blocked_by_issue: int | None = None,
        actor: str | None = None,
        repo: str | None = None,  # noqa: ARG002 - reserved for cross-repo scenarios
        event_type: str = "flow_blocked",
    ) -> None:
        """Mark flow as blocked.

        Sets flow_status="blocked" and writes blocked_reason/blocked_by_issue metadata.
        Also transitions GitHub issue label to BLOCKED state.

        Args:
            branch: Branch name
            reason: Blocking reason
            blocked_by_issue: Dependency issue number
            actor: Actor performing the block
            repo: Repository (defaults to current repo)
            event_type: Event type for timeline ("flow_blocked" or "flow_failed")
        """
        from vibe3.services.blocked_state_service import BlockedStateService

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

        issue_number: int | None = None
        from vibe3.services.issue_flow_service import IssueFlowService

        issue_flow_service = IssueFlowService(store=self.store)
        issue_number = issue_flow_service.resolve_task_issue_number(branch)

        service = BlockedStateService(store=self.store)
        service.block(
            branch=branch,
            reason=reason,
            blocked_by_issue=blocked_by_issue,
            actor=effective_actor,
            issue_number=issue_number,
            event_type=event_type,
        )

    def abort_flow(
        self: Self,
        branch: str,
        reason: str,
        actor: str | None = None,
    ) -> None:
        """Mark flow as aborted (abandoned).

        Args:
            branch: Branch name for the flow
            reason: Reason for aborting the flow
            actor: Actor performing the abort (defaults to system)
        """
        logger.bind(
            domain="flow",
            action="abort",
            branch=branch,
            reason=reason,
        ).info("Aborting flow")

        flow_data = self.store.get_flow_state(branch)
        if not flow_data:
            logger.bind(
                domain="flow",
                branch=branch,
            ).warning("Flow not found, creating minimal abort record")
            # Create minimal flow record if it doesn't exist
            self.store.update_flow_state(branch, flow_slug="aborted")

        effective_actor = SignatureService.resolve_actor(
            explicit_actor=actor,
            flow_actor=flow_data.get("latest_actor") if flow_data else None,
        )

        # Update flow state to aborted
        self.store.update_flow_state(
            branch,
            flow_status="aborted",
            latest_actor=effective_actor,
        )

        # Record abort event
        self.store.add_event(
            branch,
            "flow_aborted",
            effective_actor,
            f"Flow aborted: {reason}",
        )

        logger.bind(branch=branch).success("Flow aborted")
