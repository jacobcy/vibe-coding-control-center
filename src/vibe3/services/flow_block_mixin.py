"""Flow block/abort operations mixin."""

from typing import Self

from loguru import logger

from vibe3.clients import SQLiteClient
from vibe3.clients.github_client import GitHubClient
from vibe3.exceptions import UserError
from vibe3.models.issue_body import FlowStateProjection
from vibe3.models.orchestration import IssueState
from vibe3.services.flow_timeline_service import FlowTimelineService
from vibe3.services.issue_body_service import merge_projection
from vibe3.services.label_service import LabelService
from vibe3.services.signature_service import SignatureService


class FlowLifecycleMixin:
    """Mixin providing flow lifecycle operations."""

    store: SQLiteClient

    def _project_blocked_state(
        self: Self,
        issue_number: int,
        blocked_by_issue: int | None,
        reason: str | None,
    ) -> None:
        """Project blocked state to issue body managed section."""
        client = GitHubClient()
        current_body = client.get_issue_body(issue_number)
        if current_body is None:
            logger.bind(issue_number=issue_number).warning(
                "Failed to read issue body for projection"
            )
            return

        # Build projection
        proj = FlowStateProjection(
            state="blocked",
            blocked_by=[blocked_by_issue] if blocked_by_issue else [],
            blocked_reason=reason,
        )

        # Merge and update (short-circuit if unchanged)
        merged = merge_projection(current_body, proj)
        if merged == current_body:
            # No change, skip API call
            return

        if not client.update_issue_body(issue_number, merged):
            logger.bind(issue_number=issue_number).warning(
                "Failed to update issue body projection"
            )

    def block_flow(
        self: Self,
        branch: str,
        reason: str | None = None,
        blocked_by_issue: int | None = None,
        actor: str | None = None,
    ) -> None:
        """Mark flow as blocked.

        Note: This only writes blocked_reason/blocked_by_issue metadata.
        Blocked status is inferred from IssueState.BLOCKED label on issue.
        """
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

        # Update flow state with blocked metadata (NOT flow_status)
        # Blocked status inferred from IssueState.BLOCKED label
        self.store.update_flow_state(
            branch,
            blocked_by_issue=blocked_by_issue,
            blocked_reason=reason,
            latest_actor=effective_actor,
        )

        # Find task issue number from flow_issue_links (migrated from legacy column)
        task_issue_number: int | None = None
        issue_links = self.store.get_issue_links(branch)
        for link in issue_links:
            if link.get("issue_role") == "task":
                task_issue_number = link.get("issue_number")
                if isinstance(task_issue_number, int):
                    break

        # Transition issue state to BLOCKED if task issue exists
        if task_issue_number:
            try:
                # Transition issue state to BLOCKED
                LabelService().transition(
                    task_issue_number, IssueState.BLOCKED, effective_actor, force=False
                )
            except Exception as e:
                logger.bind(
                    domain="flow",
                    action="block",
                    branch=branch,
                    issue_number=task_issue_number,
                ).warning(f"Failed to transition issue state: {e}")

            # Add timeline comment via FlowTimelineService
            if reason:
                try:
                    timeline_service = FlowTimelineService(store=self.store)
                    timeline_service.record_timeline_event(
                        branch=branch,
                        event_type="flow_blocked",
                        actor=effective_actor,
                        detail=reason,
                        issue_number=task_issue_number,
                    )
                except Exception as e:
                    logger.bind(
                        domain="flow",
                        action="block",
                        branch=branch,
                        issue_number=task_issue_number,
                    ).warning(f"Failed to add timeline comment: {e}")

            # Project blocked state to issue body
            try:
                self._project_blocked_state(
                    task_issue_number,
                    blocked_by_issue=blocked_by_issue,
                    reason=reason,
                )
            except Exception as e:
                logger.bind(
                    domain="flow",
                    action="block",
                    branch=branch,
                    issue_number=task_issue_number,
                ).warning(f"Failed to project blocked state: {e}")

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
            Now unified with blocked: writes blocked_reason instead of
            flow_status="failed". The blocked status is inferred from
            IssueState.BLOCKED label on the task issue.
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

        # Update flow state with blocked_reason (unified with block)
        # Do NOT write flow_status - blocked inferred from issue label
        self.store.update_flow_state(
            branch,
            blocked_reason=reason,
            latest_actor=effective_actor,
        )

        # Add timeline comment via FlowTimelineService if issue linked
        issue_number = flow_data.get("task_issue_number")
        if issue_number:
            try:
                timeline_service = FlowTimelineService(store=self.store)
                timeline_service.record_timeline_event(
                    branch=branch,
                    event_type="flow_failed",
                    actor=effective_actor,
                    detail=reason,
                    issue_number=issue_number,
                )
            except Exception as e:
                logger.bind(
                    domain="flow",
                    action="fail",
                    branch=branch,
                    issue_number=issue_number,
                ).warning(f"Failed to add timeline comment: {e}")

        logger.bind(branch=branch).success("Flow marked as failed (blocked_reason)")

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
