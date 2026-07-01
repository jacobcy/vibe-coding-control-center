"""Domain service for qualify gate logic."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Any

from vibe3.clients import GitHubClient
from vibe3.domain.qualify_gate_checks import (
    check_worktree_health,
)
from vibe3.domain.qualify_gate_support import (
    terminalize_closed_issue,
)
from vibe3.models import CoordinationTruth, IssueInfo, IssueState, OrchestraConfig
from vibe3.services.flow import (
    BlockedStateService,
    FlowCleanupService,  # noqa: F401
    FlowStatusService,  # noqa: F401
)
from vibe3.services.orchestra import CoordinationResolver

if TYPE_CHECKING:
    from vibe3.clients import SQLiteClient
    from vibe3.domain.protocols.flow_protocols import FlowManagerProtocol


_ORIG_BLOCKED_STATE_SERVICE = BlockedStateService
_ORIG_FLOW_CLEANUP_SERVICE = FlowCleanupService
_ORIG_FLOW_STATUS_SERVICE = FlowStatusService


def _service_symbol(name: str, original: Any) -> Any:
    import vibe3.services as services

    local = globals().get(name, original)
    if local is not original:
        return local
    remote = getattr(services, name, original)
    return remote if remote is not original else original


class QualifyGateService:
    """Domain service for qualify gate logic."""

    def __init__(
        self,
        config: OrchestraConfig,
        github: GitHubClient,
        store: "SQLiteClient",
        flow_manager: "FlowManagerProtocol",
    ) -> None:
        self.config = config
        self._github = github
        self._store = store
        self._flow_manager = flow_manager
        self._coordination_resolver = CoordinationResolver(store=store)

    def run_qualify_gate(
        self,
        issue: IssueInfo,
        branch: str,
        flow_state: dict[str, object] | None,
        labels: list[str],
        trigger_state: IssueState,
        truth: CoordinationTruth | None = None,
    ) -> IssueState | None:
        if issue.github_state and issue.github_state.upper() == "CLOSED":
            self._terminalize_closed_issue(issue, branch)
            return None

        if truth is None:
            truth = self._coordination_resolver.resolve_coordination(
                branch, issue.number
            )

        # Active dispatch may observe authoritative blocked truth and reject
        # the candidate, but it must not invoke blocked recovery or infer a
        # normal target state. Alignment and resume belong to the explicit
        # blocked operation.
        if truth.is_blocked:
            return None

        if not flow_state:
            return trigger_state if trigger_state.to_label() in labels else None

        if not self._check_worktree_health(issue, branch, truth):
            return None

        return trigger_state if trigger_state.to_label() in labels else None

    def qualify_blocked_issue(self, issue: IssueInfo) -> IssueState | None:
        if issue.github_state and issue.github_state.upper() == "CLOSED":
            flow = self._flow_manager.get_flow_for_issue(issue.number)
            branch = str(flow.get("branch") or "").strip() if flow else ""
            self._terminalize_closed_issue(issue, branch)
            return None

        flow = self._flow_manager.get_flow_for_issue(issue.number)
        branch = str(flow.get("branch") or "").strip() if flow else ""
        if not branch:
            return None

        # Converge entirely onto reconcile_blocked
        service = BlockedStateService(store=self._store, github_client=self._github)
        target_state = service.reconcile_blocked(
            issue_number=issue.number,
            branch=branch,
            clear_reason=False,
            actor="orchestra:dispatcher",
        )
        if target_state is None:
            return None
        truth = self._coordination_resolver.resolve_coordination(branch, issue.number)
        if not self._check_worktree_health(issue, branch, truth):
            return None
        return target_state

    def _terminalize_closed_issue(self, issue: IssueInfo, branch: str) -> None:
        terminalize_closed_issue(
            issue=issue,
            branch=branch,
            store=self._store,
            github=self._github,
            flow_manager=self._flow_manager,
            flow_status_service_cls=_service_symbol(
                "FlowStatusService", _ORIG_FLOW_STATUS_SERVICE
            ),
            flow_cleanup_service_cls=_service_symbol(
                "FlowCleanupService", _ORIG_FLOW_CLEANUP_SERVICE
            ),
        )

        # Advisory notification for downstream dependents (non-blocking)
        try:
            from vibe3.services.dispatch import DependencyClosureGate

            DependencyClosureGate.notify_downstream(
                issue_number=issue.number,
                store=self._store,
                github_client=self._github,
            )
        except Exception as exc:
            # Non-critical advisory - don't block terminalization
            from loguru import logger

            logger.bind(
                domain="dispatch",
                action="terminalize_closed_issue",
                issue_number=issue.number,
                error=str(exc),
            ).warning(f"Failed to notify downstream dependents: {exc}")

    def _should_transition_to_review(
        self, branch: str, flow_state: dict[str, object] | None
    ) -> bool:
        if not flow_state or flow_state.get("flow_status") != "active":
            return False
        if not any(
            flow_state.get(status) == "running"
            for status in ("planner_status", "executor_status")
        ):
            return False
        pr = self._get_open_pr_for_branch(branch)
        if not pr:
            return False
        self._transition_flow_to_review(branch, pr)
        return True

    def _get_open_pr_for_branch(self, branch: str) -> "PRResponse | None":
        from vibe3.models import PRState

        try:
            prs = self._github.list_prs_for_branch(branch)
            return next((pr for pr in prs if pr.state == PRState.OPEN), None)
        except Exception:
            return None

    def _transition_flow_to_review(self, branch: str, pr: "PRResponse") -> None:
        transition_to_review(
            branch=branch,
            pr=pr,
            store=self._store,
            flow_manager=self._flow_manager,
            github=self._github,
            flow_status_service_cls=_service_symbol(
                "FlowStatusService", _ORIG_FLOW_STATUS_SERVICE
            ),
        )

    def _check_worktree_health(
        self,
        issue: IssueInfo,
        branch: str,
        truth: CoordinationTruth,
    ) -> bool:
        return check_worktree_health(
            issue=issue,
            branch=branch,
            truth=truth,
            store=self._store,
            github=self._github,
            config=self.config,
            path_cls=Path,
            subprocess_module=subprocess,
            blocked_state_service_cls=_service_symbol(
                "BlockedStateService", _ORIG_BLOCKED_STATE_SERVICE
            ),
            label_service_cls=_service_symbol("LabelService", None),
        )
