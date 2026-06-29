"""Flow block/abort operations mixin."""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

from loguru import logger

from vibe3.clients import SQLiteClient
from vibe3.exceptions import UserError
from vibe3.services.shared.signatures import SignatureService

if TYPE_CHECKING:
    from vibe3.services.protocols import TaskQueryProtocol


class FlowLifecycleMixin:
    """Mixin providing flow lifecycle operations."""

    store: SQLiteClient
    _task_service: "TaskQueryProtocol | None" = None

    def set_task_service(self, task_service: TaskQueryProtocol) -> None:
        """Inject task service for dependency breaking."""
        self._task_service = task_service

    def _get_task_service(self) -> "TaskQueryProtocol | None":
        """Return injected task service or None if not available."""
        return self._task_service

    def block_flow(
        self: Self,
        branch: str,
        reason: str | None = None,
        blocked_by_issue: int | None = None,
        actor: str | None = None,
        repo: str | None = None,  # noqa: ARG002 - reserved for cross-repo scenarios
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
        """
        from vibe3.services.flow.blocked_state_service import BlockedStateService

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

        issue_number: int | None = None
        from vibe3.services.issue.flow import IssueFlowService

        issue_flow_service = IssueFlowService(store=self.store)
        issue_number = issue_flow_service.resolve_task_issue_number(branch)

        service = BlockedStateService(store=self.store)
        service.set_block(
            issue_number=issue_number,
            branch=branch,
            reason=reason,
            tasks=[blocked_by_issue] if blocked_by_issue else [],
            actor=effective_actor,
        )

        # Publish FlowBlocked event if we have a valid issue context
        if issue_number is not None:
            from vibe3.models import FlowBlocked, publish

            publish(
                FlowBlocked(
                    issue_number=issue_number,
                    branch=branch,
                    blocked_reason=reason or "unspecified",
                    actor=effective_actor,
                )
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
