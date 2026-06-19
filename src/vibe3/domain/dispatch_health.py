"""Pre-dispatch health checks for orchestra dispatch."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from loguru import logger

from vibe3.domain.protocols.dispatch_protocols import FlowServiceProtocol
from vibe3.models import IssueInfo, IssueState
from vibe3.runtime import CheckServiceProtocol

if TYPE_CHECKING:
    from vibe3.clients import SQLiteClient

# Transient error prefixes: fail-open instead of blocking the flow
_TRANSIENT_ERROR_PREFIXES = ("Cannot verify", "No flow record")


class DispatchHealthService:
    """Pre-dispatch health check for branch and flow state."""

    def __init__(
        self,
        *,
        check_service: Callable[[], CheckServiceProtocol],
        store: "SQLiteClient",
        flow_blocker: FlowServiceProtocol,
        flow_context: Callable[[int], tuple[str, dict[str, object] | None]],
        emit_event: Callable[[str, str], None],
    ) -> None:
        self._check_service = check_service
        self._store = store
        self._flow_blocker = flow_blocker
        self._flow_context = flow_context
        self._emit_event = emit_event

    def check(self, issue: IssueInfo) -> bool:
        """Pre-dispatch health check. Returns True if issue can be dispatched.

        Delegates structural checks to CheckService, with terminal state
        and transient error handling inlined directly in this method.

        Flow Status Handling:
            - done/stale/review: Terminal states, skip dispatch entirely.
            - aborted: NOT terminal — return True to allow flow_manager
              recovery. flow_manager.create_flow_for_issue() performs
              branch-existence check and rebuilds the flow if missing.
              This unblocks issues stuck in OPEN + state/ready after
              flow abort without PR.

        Returns:
            True if dispatch should proceed, False to skip.
        """
        branch, _ = self._flow_context(issue.number)

        # Empty-branch guard: fail-open only for manager entry states
        if not branch:
            issue_state = issue.state
            if issue_state not in {IssueState.READY, IssueState.HANDOFF}:
                state_value = issue_state.value if issue_state else "unknown"
                self._emit_event(
                    "dispatcher",
                    f"GlobalDispatchCoordinator: skipped #{issue.number} "
                    f"(missing flow context for {state_value})",
                )
                return False
            return True

        result = self._check_service().verify_branch(branch)

        flow_state = self._store.get_flow_state(branch)
        flow_status = (
            flow_state.get("flow_status", "active") if flow_state else "active"
        )

        # Terminal state: skip dispatch cleanly
        # Exception: "aborted" needs recovery check by flow_manager
        # (rebuild if branch missing)
        if flow_status in ("done", "stale", "review"):
            self._emit_event(
                "dispatcher",
                f"GlobalDispatchCoordinator: skipped #{issue.number} "
                f"(flow is {flow_status})",
            )
            return False

        # Aborted flow: let flow_manager handle recovery (rebuild if branch missing).
        # flow_manager.create_flow_for_issue() checks branch and rebuilds.
        if flow_status == "aborted":
            self._emit_event(
                "dispatcher",
                f"GlobalDispatchCoordinator: allowing aborted #{issue.number} "
                f"for flow_manager recovery check",
            )
            return True

        if not result.is_valid:
            # Transient errors: fail-open
            is_transient = any(
                any(err.startswith(prefix) for err in result.issues)
                for prefix in _TRANSIENT_ERROR_PREFIXES
            )
            if is_transient:
                self._emit_event(
                    "dispatcher",
                    f"GlobalDispatchCoordinator: fail-open for #{issue.number} "
                    f"(transient: {', '.join(result.issues)})",
                )
                return True

            # Genuine failure: block and skip
            reason = f"Health check failed: {', '.join(result.issues)}"
            block_succeeded = False
            try:
                self._flow_blocker.block_flow(
                    branch=branch, reason=reason, actor="orchestra:dispatcher"
                )
                block_succeeded = True
            except Exception as exc:
                logger.bind(domain="orchestra", action="health_check").warning(
                    f"Failed to block flow for #{issue.number}: {exc}"
                )
                self._emit_event(
                    "dispatcher",
                    f"GlobalDispatchCoordinator: block_failed #{issue.number} "
                    f"(error: {exc}, health check: {reason})",
                )

            if block_succeeded:
                self._emit_event(
                    "dispatcher",
                    f"GlobalDispatchCoordinator: blocked #{issue.number} "
                    f"(health check failed: {reason})",
                )
            return False

        return True
