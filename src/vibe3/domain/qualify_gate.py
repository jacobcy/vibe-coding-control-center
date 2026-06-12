"""Domain service for qualify gate logic."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Any

from vibe3.clients import GitHubClient
from vibe3.config import get_convention
from vibe3.domain.qualify_gate_checks import (
    check_dependencies,
    check_worktree_health,
    get_issue_dependencies,
    is_dependency_satisfied,
)
from vibe3.domain.qualify_gate_support import (
    align_blocked_state,
    auto_resume_blocked,
    has_stale_blocked_state,
    resume_dep_resolved,
    terminalize_closed_issue,
    transition_to_review,
)
from vibe3.models import CoordinationTruth, IssueInfo, IssueState, OrchestraConfig
from vibe3.services import (
    BlockedStateService,  # noqa: F401
    CoordinationResolver,
    FlowCleanupService,  # noqa: F401
    FlowService,  # noqa: F401
    FlowStatusService,  # noqa: F401
    IssueFlowService,  # noqa: F401
    LabelService,  # noqa: F401
    TaskResumeOperations,
    infer_resume_label,
)

if TYPE_CHECKING:
    from vibe3.clients import SQLiteClient
    from vibe3.domain.protocols.flow_protocols import FlowManagerProtocol
    from vibe3.models import PRResponse


_ORIG_BLOCKED_STATE_SERVICE = BlockedStateService
_ORIG_FLOW_CLEANUP_SERVICE = FlowCleanupService
_ORIG_FLOW_SERVICE = FlowService
_ORIG_FLOW_STATUS_SERVICE = FlowStatusService
_ORIG_ISSUE_FLOW_SERVICE = IssueFlowService
_ORIG_LABEL_SERVICE = LabelService


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

        if truth.is_blocked:
            self._align_blocked_state(
                issue_number=issue.number,
                branch=branch,
                truth=truth,
                labels=labels,
                flow_state=flow_state,
            )
            return None

        if self._has_stale_blocked_state(truth, labels, flow_state):
            target_label = self._auto_resume_blocked(
                issue_number=issue.number,
                branch=branch,
                flow_state=flow_state,
            )
            flow_state = self._store.get_flow_state(branch)
            if not flow_state:
                return target_label

        if not flow_state:
            return trigger_state if trigger_state.to_label() in labels else None

        if not self._check_worktree_health(issue, branch, truth):
            return None

        if not self._check_dependencies(issue, branch, truth, labels):
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

        truth = self._coordination_resolver.resolve_coordination(branch, issue.number)
        if truth.blocked_reason:
            if truth.is_blocked:
                self._align_blocked_state(
                    issue.number,
                    branch,
                    truth,
                    list(issue.labels),
                    self._store.get_flow_state(branch),
                )
            return None

        if truth.is_blocked and truth.blocked_by_issues:
            all_satisfied = all(
                self._is_dependency_satisfied(dep) for dep in truth.blocked_by_issues
            )
            if all_satisfied:
                return self._resume_dep_resolved(
                    branch, issue.number, truth.blocked_by_issues
                )

            from vibe3.observability import append_orchestra_event

            open_deps = [
                dep
                for dep in truth.blocked_by_issues
                if not self._is_dependency_satisfied(dep)
            ]
            append_orchestra_event(
                "dispatcher",
                "qualify_gate skip #"
                f"{issue.number}: blocked by dependencies {open_deps} "
                "(some still open)",
            )
            return None

        flow_state = self._store.get_flow_state(branch)
        result = self.run_qualify_gate(
            issue,
            branch,
            flow_state,
            list(issue.labels),
            IssueState.BLOCKED,
            truth=truth,
        )
        return None if result == IssueState.BLOCKED else result

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

    def _resume_dep_resolved(
        self, branch: str, issue_number: int, dep_issue_numbers: list[int]
    ) -> IssueState:
        return resume_dep_resolved(
            branch=branch,
            issue_number=issue_number,
            dep_issue_numbers=dep_issue_numbers,
            store=self._store,
            github=self._github,
            config=self.config,
            blocked_state_service_cls=_service_symbol(
                "BlockedStateService", _ORIG_BLOCKED_STATE_SERVICE
            ),
            label_service_cls=_service_symbol("LabelService", _ORIG_LABEL_SERVICE),
            infer_resume_label_fn=infer_resume_label,
        )

    def _align_blocked_state(
        self,
        issue_number: int,
        branch: str,
        truth: CoordinationTruth,
        labels: list[str],
        flow_state: dict[str, object] | None,
    ) -> None:
        align_blocked_state(
            issue_number=issue_number,
            branch=branch,
            truth=truth,
            labels=labels,
            flow_state=flow_state,
            blocked_label=self._blocked_label,
            store=self._store,
            github=self._github,
            config=self.config,
            blocked_state_service_cls=_service_symbol(
                "BlockedStateService", _ORIG_BLOCKED_STATE_SERVICE
            ),
            label_service_cls=_service_symbol("LabelService", _ORIG_LABEL_SERVICE),
        )

    def _has_stale_blocked_state(
        self,
        truth: CoordinationTruth,
        labels: list[str],
        flow_state: dict[str, object] | None,
    ) -> bool:
        return has_stale_blocked_state(
            labels=labels,
            flow_state=flow_state,
            blocked_label=self._blocked_label,
        )

    def _source_value(self, source: object | None) -> str:
        return str(value) if (value := getattr(source, "value", None)) else "none"

    def _format_blocked_skip_event(
        self,
        *,
        issue_number: int,
        truth: CoordinationTruth,
        flow_state: dict[str, object] | None,
        label_blocked: bool,
    ) -> str:
        from vibe3.domain.qualify_gate_support import format_blocked_skip_event

        return format_blocked_skip_event(
            issue_number=issue_number,
            truth=truth,
            flow_state=flow_state,
            label_blocked=label_blocked,
        )

    def _auto_resume_blocked(
        self,
        issue_number: int,
        branch: str,
        flow_state: dict[str, object] | None,
    ) -> IssueState:
        return auto_resume_blocked(
            issue_number=issue_number,
            branch=branch,
            flow_state=flow_state,
            store=self._store,
            github=self._github,
            config=self.config,
            task_resume_operations_cls=TaskResumeOperations,
            flow_service_cls=_service_symbol("FlowService", _ORIG_FLOW_SERVICE),
            label_service_cls=_service_symbol("LabelService", _ORIG_LABEL_SERVICE),
            issue_flow_service_cls=_service_symbol(
                "IssueFlowService", _ORIG_ISSUE_FLOW_SERVICE
            ),
            infer_resume_label_fn=infer_resume_label,
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
            label_service_cls=_service_symbol("LabelService", _ORIG_LABEL_SERVICE),
        )

    def _check_dependencies(
        self,
        issue: IssueInfo,
        branch: str,
        truth: CoordinationTruth,
        _labels: list[str],
    ) -> bool:
        return check_dependencies(
            issue=issue,
            branch=branch,
            truth=truth,
            store=self._store,
            github=self._github,
            config=self.config,
            is_dependency_satisfied_fn=self._is_dependency_satisfied,
            blocked_state_service_cls=_service_symbol(
                "BlockedStateService", _ORIG_BLOCKED_STATE_SERVICE
            ),
            label_service_cls=_service_symbol("LabelService", _ORIG_LABEL_SERVICE),
        )

    def _get_issue_dependencies(self, issue_number: int) -> list[int]:
        return get_issue_dependencies(issue_number=issue_number, store=self._store)

    def _is_dependency_satisfied(self, dep_issue_number: int) -> bool:
        return is_dependency_satisfied(
            github=self._github,
            config=self.config,
            dep_issue_number=dep_issue_number,
        )
