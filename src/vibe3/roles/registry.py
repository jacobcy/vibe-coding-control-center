"""Role registry aggregating all dispatchable roles."""

from __future__ import annotations

from pathlib import Path

from vibe3.domain.events import (
    ExecutorDispatched,
    PlannerDispatched,
    ReviewerDispatched,
)
from vibe3.domain.events.flow_lifecycle import IssueStateChanged
from vibe3.environment.session_registry import SessionRegistryService
from vibe3.execution.contracts import ExecutionRequest
from vibe3.execution.issue_role_support import resolve_orchestra_repo_root
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.models.orchestration import IssueInfo, IssueState
from vibe3.roles.definitions import TriggerableRoleDefinition
from vibe3.roles.manager import (
    HANDOFF_MANAGER_ROLE,
    MANAGER_ROLE,
    build_manager_request,
)
from vibe3.roles.plan import (
    PLANNER_ROLE,
)
from vibe3.roles.review import (
    REVIEWER_ROLE,
)
from vibe3.roles.run import (
    EXECUTOR_ROLE,
)

LABEL_DISPATCH_ROLES: tuple[TriggerableRoleDefinition, ...] = (
    MANAGER_ROLE,
    HANDOFF_MANAGER_ROLE,
    PLANNER_ROLE,
    EXECUTOR_ROLE,
    REVIEWER_ROLE,
)


def resolve_issue_state_role(to_state: str) -> TriggerableRoleDefinition | None:
    """Resolve the triggerable role definition for an IssueStateChanged event."""
    if to_state == IssueState.READY.value:
        return MANAGER_ROLE
    if to_state == IssueState.HANDOFF.value:
        return HANDOFF_MANAGER_ROLE
    return None


def build_issue_state_request(
    config: OrchestraConfig,
    issue: IssueInfo,
    to_state: str,
    *,
    registry: SessionRegistryService | None = None,
    repo_path: Path | None = None,
) -> ExecutionRequest | None:
    """Build a role request from IssueStateChanged when a role supports it."""
    role = resolve_issue_state_role(to_state)
    if role is None:
        return None
    if role.registry_role == "manager":
        return build_manager_request(
            config,
            issue,
            registry=registry,
            repo_path=repo_path or resolve_orchestra_repo_root(),
        )
    return None


def build_label_dispatch_event(
    role: TriggerableRoleDefinition,
    issue: IssueInfo,
    *,
    branch: str,
    flow_state: dict[str, object] | None,
) -> IssueStateChanged | PlannerDispatched | ExecutorDispatched | ReviewerDispatched:
    """Build the authoritative domain event for a label-triggered role."""
    trigger = role.trigger_name
    if trigger == "manager":
        return IssueStateChanged(
            issue_number=issue.number,
            from_state=None,
            to_state=role.trigger_state.value,
            issue_title=issue.title if issue.title else None,
        )
    if trigger == "plan":
        return PlannerDispatched(
            issue_number=issue.number,
            branch=branch,
            trigger_state=IssueState.CLAIMED.value,
        )
    if trigger == "run":
        plan_ref = flow_state.get("plan_ref") if flow_state else None
        return ExecutorDispatched(
            issue_number=issue.number,
            branch=branch,
            trigger_state=IssueState.IN_PROGRESS.value,
            plan_ref=str(plan_ref) if plan_ref else None,
        )
    if trigger == "review":
        report_ref = flow_state.get("report_ref") if flow_state else None
        return ReviewerDispatched(
            issue_number=issue.number,
            branch=branch,
            trigger_state=IssueState.REVIEW.value,
            report_ref=str(report_ref) if report_ref else None,
        )
    return IssueStateChanged(
        issue_number=issue.number,
        from_state=None,
        to_state=role.trigger_state.value,
        issue_title=issue.title if issue.title else None,
    )
