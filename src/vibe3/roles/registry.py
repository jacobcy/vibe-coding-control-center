"""Role registry aggregating all dispatchable roles."""

from __future__ import annotations

from pathlib import Path

from vibe3.environment.session_registry import SessionRegistryService
from vibe3.execution.contracts import ExecutionRequest
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.models.orchestration import IssueInfo, IssueState
from vibe3.roles.definitions import TriggerableRoleDefinition
from vibe3.roles.manager import (
    HANDOFF_MANAGER_ROLE,
    MANAGER_ROLE,
    build_manager_request,
    resolve_orchestra_repo_root,
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
