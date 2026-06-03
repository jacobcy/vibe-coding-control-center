"""Pre-dispatch health check service for orchestra dispatcher.

This service validates structural health before dispatch:
- Issue closed / PR merged (terminal)
- Missing worktree / invalid refs
- Transient fail-open (network/auth errors, missing flow records)
- Terminal flow states (done/aborted/stale)

Blocked/unblocked truth reconciliation is handled by qualify-gate,
not by this health check.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from loguru import logger

from vibe3.orchestra import IssueInfo, IssueState, append_orchestra_event
from vibe3.orchestra.protocols import (
    CheckServiceProtocol,
    FlowServiceProtocol,
)

if TYPE_CHECKING:
    from vibe3.clients.sqlite_client import SQLiteClient


class DispatchHealthCheckService:
    """Pre-dispatch health check service.

    SCOPE: Structural validity only. Does NOT make blocked semantic decisions.
    Those belong in qualify-gate. Only validates structural health.

    Returns True if issue can be dispatched (healthy or transient error).
    Returns False if issue should be skipped (genuine failure or terminal state).
    """

    def __init__(
        self,
        check_service: CheckServiceProtocol,
        flow_blocker: FlowServiceProtocol,
        store: "SQLiteClient",
        flow_context_resolver: Callable[[int], tuple[str, dict[str, object] | None]],
    ) -> None:
        """Initialize health check service.

        Args:
            check_service: Service for verifying branch flow consistency
            flow_blocker: Service for blocking flows
            store: SQLite client for flow state queries
            flow_context_resolver: Callable to resolve branch from issue number
        """
        self._check_service = check_service
        self._flow_blocker = flow_blocker
        self._store = store
        self._flow_context_resolver = flow_context_resolver

    def check_issue_health(self, issue: IssueInfo) -> bool:
        """Check structural health before dispatch.

        Args:
            issue: Issue to check

        Returns:
            True if issue can be dispatched (healthy or transient error)
            False if issue should be skipped (genuine failure or terminal state)
        """
        # Get the canonical branch for this issue
        branch, _ = self._flow_context_resolver(issue.number)

        # If no branch exists, fail open only for manager entry states
        # that can create a fresh task scene. Worker states require an
        # existing flow context; otherwise role builders fall back to a
        # canonical branch that may not exist, causing invalid worktree dispatch.
        if not branch:
            issue_state = issue.state
            if issue_state not in {IssueState.READY, IssueState.HANDOFF}:
                state_value = issue_state.value if issue_state else "unknown"
                append_orchestra_event(
                    "dispatcher",
                    f"DispatchHealthCheckService: skipped #{issue.number} "
                    f"(missing flow context for {state_value})",
                )
                return False
            return True

        # Use CheckService for unified health check
        result = self._check_service.verify_branch(branch)

        # Get flow status BEFORE checking result.is_valid.
        # verify_branch() may have just written an abort; reading here ensures
        # we see the updated state and avoid calling block_flow on terminal flows.
        flow_state = self._store.get_flow_state(branch)
        flow_status = (
            flow_state.get("flow_status", "active") if flow_state else "active"
        )

        # Terminal state takes priority: skip dispatch cleanly without block_flow.
        # This handles flows auto-aborted by verify_branch (closed issue, missing
        # branch, orphaned flow) as well as flows already in done/stale state.
        if flow_status in ("done", "aborted", "stale"):
            append_orchestra_event(
                "dispatcher",
                f"DispatchHealthCheckService: skipped #{issue.number} "
                f"(flow is {flow_status})",
            )
            return False

        # Determine dispatch eligibility for non-terminal flows:
        # - Fail-open for transient errors (network/auth) and missing flow records
        # - Return False for genuine consistency failures (issue closed, PR merged)
        if not result.is_valid:
            # Check if this is a transient/expected error that should fail-open
            transient_errors = [
                "Cannot verify",  # Network/auth errors
                "No flow record",  # Missing flow_state (new issues)
            ]
            is_transient = any(
                any(err.startswith(prefix) for err in result.issues)
                for prefix in transient_errors
            )

            if is_transient:
                # Fail-open: allow dispatch despite transient errors
                append_orchestra_event(
                    "dispatcher",
                    f"DispatchHealthCheckService: fail-open for #{issue.number} "
                    f"(transient error: {', '.join(result.issues)})",
                )
                return True

            # Genuine consistency failure - block and skip dispatch
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
                append_orchestra_event(
                    "dispatcher",
                    f"DispatchHealthCheckService: block_failed #{issue.number} "
                    f"(error: {exc}, health check: {reason})",
                )

            if block_succeeded:
                append_orchestra_event(
                    "dispatcher",
                    f"DispatchHealthCheckService: blocked #{issue.number} "
                    f"(health check failed: {reason})",
                )
            return False

        return True
