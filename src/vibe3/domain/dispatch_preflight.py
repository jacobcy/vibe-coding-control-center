"""Unified pre-dispatch checks for orchestra dispatch."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from loguru import logger

from vibe3.exceptions.error_codes import E_DISPATCH_FAILURE
from vibe3.models import IssueInfo, IssueState
from vibe3.observability import append_orchestra_event, get_degraded_manager
from vibe3.services.orchestra import record_error


class QualifyGateLike(Protocol):
    """Subset of QualifyGate used by dispatch preflight."""

    def qualify_blocked_issue(self, issue: IssueInfo) -> IssueState | None:
        """Qualify a blocked issue for dispatch."""
        ...

    def run_qualify_gate(
        self,
        issue: IssueInfo,
        branch: str,
        flow_state: dict[str, object] | None,
        labels: list[str],
        trigger_state: IssueState,
    ) -> IssueState | None:
        """Run semantic dispatch qualification for an issue."""
        ...


@dataclass(frozen=True)
class DispatchPreflightDecision:
    """Result of unified pre-dispatch checks."""

    allowed: bool
    target_state: IssueState | None
    reason: str = ""


class DispatchPreflightService:
    """Converges semantic and structural dispatch checks."""

    def __init__(
        self,
        *,
        qualify_gate: QualifyGateLike,
        flow_context: Callable[[int], tuple[str, dict[str, object] | None]],
        structural_check: Callable[[IssueInfo], bool],
    ) -> None:
        self._qualify_gate = qualify_gate
        self._flow_context = flow_context
        self._structural_check = structural_check

    def evaluate(self, issue: IssueInfo) -> DispatchPreflightDecision:
        """Run semantic and structural checks before dispatch intent emission."""
        if issue.state is None:
            return DispatchPreflightDecision(False, None, "missing issue state")

        if issue.state == IssueState.BLOCKED:
            target_state = self._qualify_blocked(issue)
        else:
            target_state = self._qualify_active(issue)

        if target_state is None:
            return DispatchPreflightDecision(False, None, "qualify gate rejected")

        if not self._structural_check(issue):
            return DispatchPreflightDecision(False, None, "health check failed")

        return DispatchPreflightDecision(True, target_state)

    def _qualify_blocked(self, issue: IssueInfo) -> IssueState | None:
        try:
            target_state = self._qualify_gate.qualify_blocked_issue(issue)
        except BaseException as exc:
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                raise
            append_orchestra_event(
                "dispatcher",
                f"GlobalDispatchCoordinator: preflight skipped #{issue.number} "
                f"(blocked qualify gate failed: {exc})",
            )
            logger.bind(domain="orchestra", action="dispatch_preflight").warning(
                f"Blocked qualify gate failed for #{issue.number}: {exc}"
            )
            try:
                record_error(
                    error_code=E_DISPATCH_FAILURE,
                    error_message=(
                        f"dispatch_preflight blocked qualify gate failed for "
                        f"#{issue.number}: {exc}"
                    ),
                    issue_number=issue.number,
                )
            except Exception as record_exc:
                logger.bind(
                    domain="orchestra", action="dispatch_preflight_record_error"
                ).warning(f"Failed to record dispatch_preflight error: {record_exc}")
            return None

        degraded = get_degraded_manager()
        if degraded.is_degraded():
            degraded_reason = degraded.get_reason()
            reason_value = degraded_reason.value if degraded_reason else None
            logger.bind(
                domain="orchestra",
                action="collect_blocked_intents",
                degraded_mode=True,
                reason=reason_value,
                issue_number=issue.number,
            ).warning(f"Qualification of #{issue.number} entered degraded mode")

        return target_state

    def _qualify_active(self, issue: IssueInfo) -> IssueState | None:
        trigger_state = issue.state
        if trigger_state is None:
            return None

        branch, flow_state = self._flow_context(issue.number)
        if not branch and trigger_state not in {IssueState.READY, IssueState.HANDOFF}:
            if not self._structural_check(issue):
                return None

        try:
            return self._qualify_gate.run_qualify_gate(
                issue,
                branch,
                flow_state,
                issue.labels,
                trigger_state,
            )
        except BaseException as exc:
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                raise
            append_orchestra_event(
                "dispatcher",
                f"GlobalDispatchCoordinator: preflight skipped #{issue.number} "
                f"(qualify gate failed: {exc})",
            )
            logger.bind(domain="orchestra", action="dispatch_preflight").warning(
                f"Qualify gate failed for #{issue.number}: {exc}"
            )
            try:
                record_error(
                    error_code=E_DISPATCH_FAILURE,
                    error_message=(
                        f"dispatch_preflight active qualify gate failed for "
                        f"#{issue.number}: {exc}"
                    ),
                    issue_number=issue.number,
                )
            except Exception as record_exc:
                logger.bind(
                    domain="orchestra", action="dispatch_preflight_record_error"
                ).warning(f"Failed to record dispatch_preflight error: {record_exc}")
            return None
