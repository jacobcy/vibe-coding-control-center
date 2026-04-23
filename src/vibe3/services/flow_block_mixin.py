"""Flow block/abort operations mixin."""

from typing import Self

from loguru import logger

from vibe3.clients import SQLiteClient
from vibe3.exceptions import UserError
from vibe3.models.orchestration import IssueState
from vibe3.services.label_service import LabelService
from vibe3.services.signature_service import SignatureService


def sync_flow_blocked_task_label(store: SQLiteClient, branch: str) -> None:
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


def sync_flow_done_task_label(store: SQLiteClient, branch: str) -> None:
    """Sync task-role issues in a flow to state/done when flow is done."""
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
            IssueState.DONE,
            actor="flow:done",
            force=True,
        )


class FlowLifecycleMixin:
    """Mixin providing flow lifecycle operations."""

    store: SQLiteClient

    def block_flow(
        self: Self,
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

        # Link dependency issue if provided
        if blocked_by_issue:
            from vibe3.services.task_service import TaskService

            TaskService().link_issue(
                branch,
                blocked_by_issue,
                role="dependency",
                actor=effective_actor,
            )

        # Update flow state with new field structure (semantic clarity)
        # blocked_by_issue: dependency issue number (INT)
        # blocked_reason: block reason text (TEXT)
        self.store.update_flow_state(
            branch,
            flow_status="blocked",
            blocked_by_issue=blocked_by_issue,
            blocked_reason=reason,
            latest_actor=effective_actor,
        )

        self.store.add_event(
            branch,
            "flow_blocked",
            effective_actor,
            f"Flow blocked{': ' + reason if reason else ''}",
        )
        sync_flow_blocked_task_label(self.store, branch)

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
            Failed flows indicate execution errors or system faults requiring
            human intervention before they can continue. Recovery path: Ready.
        """
        logger.bind(
            domain="flow",
            action="fail",
            branch=branch,
            reason=reason,
        ).info("Failing flow")

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

        # Update flow state to failed with failure reason
        self.store.update_flow_state(
            branch,
            flow_status="failed",
            failed_reason=reason,
            latest_actor=effective_actor,
        )

        # Record fail event
        self.store.add_event(
            branch,
            "flow_failed",
            effective_actor,
            f"Flow failed: {reason}",
        )

        logger.bind(branch=branch).success("Flow marked as failed")

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
