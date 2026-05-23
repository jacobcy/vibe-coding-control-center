"""Flow block/abort operations mixin."""

from typing import Self

from loguru import logger

from vibe3.clients import SQLiteClient
from vibe3.exceptions import UserError
from vibe3.services.flow_timeline_service import FlowTimelineService
from vibe3.services.signature_service import SignatureService


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
        issue_links = self.store.get_issue_links(branch)
        for link in issue_links:
            if link.get("issue_role") == "task":
                issue_number = link.get("issue_number")
                if isinstance(issue_number, int):
                    break

        service = BlockedStateService(store=self.store)
        service.block(
            branch=branch,
            reason=reason,
            blocked_by_issue=blocked_by_issue,
            actor=effective_actor,
            issue_number=issue_number,
            event_type=event_type,
        )

    def fail_flow(
        self: Self,
        branch: str,
        reason: str,
        actor: str | None = None,
    ) -> None:
        """Mark flow as failed (execution error, system fault).

        Args:
            branch: Branch name for the flow
            reason: Failure reason (required)
            actor: Actor performing the fail (defaults to system)

        Note:
            Failed flows indicate execution errors or system faults.
            This method records to error_log and timeline only - it does NOT
            trigger business block (no blocked_reason, no label change).
            Runtime errors are handled by ERROR system, not BLOCK system.
        """
        from vibe3.exceptions.error_codes import E_EXEC_FLOW_FAILURE
        from vibe3.services.error_tracking_service import ErrorTrackingService

        logger.bind(
            domain="flow",
            action="fail",
            branch=branch,
            reason=reason,
        ).info("Failing flow (runtime error)")

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

        issue_number = flow_data.get("task_issue_number")
        if not issue_number:
            issue_links = self.store.get_issue_links(branch)
            for link in issue_links:
                if link.get("issue_role") == "task":
                    issue_number = link.get("issue_number")
                    if isinstance(issue_number, int):
                        break

        error_tracking = ErrorTrackingService.get_instance(store=self.store)
        error_tracking.record_error(
            error_code=E_EXEC_FLOW_FAILURE,
            error_message=reason,
            branch=branch,
            issue_number=issue_number,
        )

        timeline = FlowTimelineService(store=self.store)
        timeline.record_timeline_event(
            branch=branch,
            event_type="flow_failed",
            actor=effective_actor,
            detail=f"Flow failed (runtime): {reason}",
            issue_number=issue_number,
        )

        logger.bind(branch=branch).success(
            "Flow marked as failed (error_log only, no block)"
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
