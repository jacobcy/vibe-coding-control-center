"""Domain service for qualify gate logic."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Any

from vibe3.clients import GitHubClient
from vibe3.config import get_convention
from vibe3.domain.qualify_gate_checks import (
    check_worktree_health,
    get_issue_dependencies,
)
from vibe3.domain.qualify_gate_support import (
    terminalize_closed_issue,
    transition_to_review,
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
    from vibe3.models import PRResponse


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
        self._convention = get_convention()
        self._blocked_label = self._convention.state_label(
            self._convention.blocked_label
        )
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

        if branch and self._should_transition_to_review(branch, flow_state):
            return None

        if truth is None:
            truth = self._coordination_resolver.resolve_coordination(
                branch, issue.number
            )

        # 收敛：blocked/stale 一律走 reconcile_blocked（body 为真源）。
        # 触发用便宜信号(body真源 truth.is_blocked, 或 label/cache 的 stale 信号)。
        blocked_signal = (
            truth.is_blocked
            or self._blocked_label in labels
            or (flow_state is not None and flow_state.get("flow_status") == "blocked")
        )
        if branch and blocked_signal:
            reconcile_result = BlockedStateService(
                store=self._store, github_client=self._github
            ).reconcile_blocked(
                issue.number,
                branch,
                clear_reason=False,
                actor="orchestra:dispatcher",
            )
            flow_state = self._store.get_flow_state(branch)
            if not flow_state or flow_state.get("flow_status") == "blocked":
                return None  # 仍阻塞或降级 -> 不派发
            if reconcile_result is not None:
                return reconcile_result  # 已解除阻塞 -> 派发重建后的目标状态

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

    def _get_issue_dependencies(self, issue_number: int) -> list[int]:
        return get_issue_dependencies(issue_number=issue_number, store=self._store)
