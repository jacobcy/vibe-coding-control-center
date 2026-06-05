"""Shared role definition types and base classes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Literal

from vibe3.clients import SQLiteClient
from vibe3.config.role_policy import RoleOutputContract
from vibe3.models import IssueInfo, IssueState
from vibe3.models.execution_request import ExecutionRequest
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.models.session_types import SessionRole
from vibe3.models.worktree import WorktreeRequirement

TriggerName = Literal["manager", "plan", "run", "review", "blocked"]


@dataclass(frozen=True)
class RoleDefinition:
    """Minimal declarative definition for a runtime role."""

    name: str
    registry_role: str
    worktree: WorktreeRequirement
    trigger_name: TriggerName | None = None
    trigger_state: IssueState | None = None
    output_contract: RoleOutputContract = field(default_factory=RoleOutputContract)


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
    resolve_options: Callable[[OrchestraConfig, dict[str, str] | None], Any]
    resolve_branch: Callable[[SQLiteClient, int, str], str]
    build_async_request: Callable[
        [OrchestraConfig, IssueInfo, str, str], ExecutionRequest | None
    ]
    build_sync_request: Callable[
        [
            OrchestraConfig,
            IssueInfo,
            str,
            dict[str, object] | None,
            str | None,
            Any,
            str,
            bool,
            bool,
        ],
        ExecutionRequest,
    ]
    failure_handler: Callable[..., None] | None = None
