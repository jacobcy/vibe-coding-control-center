"""Manager run post-execution coordinator.

This module handles post-run orchestration for manager execution,
separating lifecycle coordination from the runtime entrypoint.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vibe3.models.orchestration import IssueState
from vibe3.runtime.no_progress_policy import has_progress_changed
from vibe3.services.abandon_flow_service import AbandonFlowService
from vibe3.services.issue_failure_service import block_manager_noop_issue

if TYPE_CHECKING:
    from vibe3.clients.sqlite_client import SQLiteClient


class ManagerRunCoordinator:
    """Coordinates post-run manager lifecycle.

    This coordinator handles:
    - Post-run abandon flow orchestration
    - Progress checking and no-op blocking
    - Event recording for manager outcomes
    """

    def __init__(self, store: SQLiteClient) -> None:
        """Initialize coordinator.

        Args:
            store: SQLite client for flow state
        """
        self._store = store

    def handle_post_run_outcome(
        self,
        *,
        issue_number: int,
        branch: str,
        actor: str,
        repo: str | None,
        before_snapshot: dict[str, object],
        after_snapshot: dict[str, object],
    ) -> bool:
        """Handle post-run close/abandon outcomes.

        Returns True when the outcome was fully handled and the caller should stop.
        """
        if after_snapshot.get("issue_state") != "closed":
            return False

        before_state_label = before_snapshot.get("state_label", "")
        source_state: IssueState | None = None
        if before_state_label == "state/ready":
            source_state = IssueState.READY
        elif before_state_label == "state/handoff":
            source_state = IssueState.HANDOFF

        if source_state is None:
            self._store.add_event(
                branch,
                "manager_closed_issue_unexpected_state",
                actor,
                detail=(
                    f"Issue #{issue_number} closed but was in {before_state_label} "
                    f"(expected state/ready or state/handoff)"
                ),
                refs={"issue": str(issue_number)},
            )
            return True

        abandon_service = AbandonFlowService()
        abandon_result = abandon_service.abandon_flow(
            issue_number=issue_number,
            branch=branch,
            source_state=source_state,
            reason="manager closed issue without finalizing abandon flow",
            actor=actor,
            issue_already_closed=True,
            flow_already_aborted=after_snapshot.get("flow_status") == "aborted",
        )
        self._store.add_event(
            branch,
            "manager_abandoned_flow",
            actor,
            detail=(
                f"Manager abandoned flow for issue #{issue_number} "
                f"(issue={abandon_result.get('issue')}, "
                f"pr={abandon_result.get('pr')}, "
                f"flow={abandon_result.get('flow')})"
            ),
            refs={"issue": str(issue_number), "result": str(abandon_result)},
        )
        return True

    def check_progress_and_block_if_noop(
        self,
        *,
        issue_number: int,
        branch: str,
        actor: str,
        repo: str | None,
        before_snapshot: dict[str, object],
        after_snapshot: dict[str, object],
    ) -> bool:
        """Check if manager made progress, block if no-op.

        Returns True if manager was blocked (caller should stop).
        """
        # Manager must leave READY or HANDOFF state to count as progress
        current_state_label = before_snapshot.get("state_label", "")
        allow_close = current_state_label in ("state/ready", "state/handoff")
        if not has_progress_changed(
            before_snapshot,
            after_snapshot,
            require_state_transition=True,
            allow_close_as_progress=allow_close,
        ):
            reason = (
                "manager 本轮未产生状态迁移（must leave READY/HANDOFF per contract）"
            )
            self._store.add_event(
                branch,
                "manager_noop_blocked",
                actor,
                detail=f"Manager auto-blocked issue #{issue_number}: {reason}",
                refs={"issue": str(issue_number), "reason": reason},
            )
            block_manager_noop_issue(
                issue_number=issue_number,
                repo=repo,
                reason=reason,
                actor=actor,
            )
            return True
        return False
