"""Shared role definition types and base classes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Literal

from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.execution.contracts import ExecutionRequest
from vibe3.execution.role_contracts import WorktreeRequirement
from vibe3.execution.session_service import SessionRole
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.models.orchestration import IssueInfo, IssueState

TriggerName = Literal["manager", "plan", "run", "review"]


@dataclass(frozen=True)
class RoleDefinition:
    """Minimal declarative definition for a runtime role."""

    name: str
    registry_role: str
    worktree: WorktreeRequirement
    trigger_name: TriggerName | None = None
    trigger_state: IssueState | None = None


@dataclass(frozen=True)
class TriggerableRoleDefinition(RoleDefinition):
    """Role definition with mandatory trigger fields for label dispatch.

    Extends RoleDefinition with per-role dispatch gating logic so that
    StateLabelDispatchService does not need role-specific if/elif chains.

    Attributes:
        trigger_name: TriggerName used to identify this role in dispatch.
        trigger_state: IssueState label that activates this role.
        dispatch_predicate: (flow_state, has_live_session) -> bool controlling
            whether an issue should be dispatched for this role.
    """

    trigger_name: TriggerName  # type: ignore[override]
    trigger_state: IssueState  # type: ignore[override]
    dispatch_predicate: Callable[[dict[str, object], bool], bool] = field(
        default=lambda _flow, has_live: not has_live,
        compare=False,
        hash=False,
    )


@dataclass(frozen=True)
class IssueRoleSyncSpec:
    """Role-owned hooks for the generic issue sync runner."""

    role_name: SessionRole
    resolve_options: Callable[[OrchestraConfig], Any]
    resolve_branch: Callable[[SQLiteClient, int, str], str]
    build_async_request: Callable[
        [OrchestraConfig, IssueInfo, str], ExecutionRequest | None
    ]
    build_sync_request: Callable[
        [OrchestraConfig, IssueInfo, str, str | None, Any, str, bool], ExecutionRequest
    ]
    failure_handler: Callable[..., None] | None = None
