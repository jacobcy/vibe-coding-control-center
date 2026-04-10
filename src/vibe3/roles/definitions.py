"""Shared role definition types and base classes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Literal

from vibe3.agents.session_service import SessionRole
from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.execution.contracts import ExecutionRequest
from vibe3.execution.role_contracts import RoleGateConfig
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.models.orchestration import IssueInfo, IssueState

TriggerName = Literal["manager", "plan", "run", "review"]


@dataclass(frozen=True)
class RoleDefinition:
    """Minimal declarative definition for a runtime role."""

    name: str
    registry_role: str
    gate_config: RoleGateConfig
    trigger_name: TriggerName | None = None
    trigger_state: IssueState | None = None


@dataclass(frozen=True)
class TriggerableRoleDefinition(RoleDefinition):
    """Role definition with mandatory trigger fields for label dispatch."""

    trigger_name: TriggerName  # type: ignore[override]
    trigger_state: IssueState  # type: ignore[override]


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
    snapshot_progress: Callable[..., dict[str, object]] | None = None
    post_sync_hook: (
        Callable[
            [
                SQLiteClient,
                int,
                str,
                str,
                OrchestraConfig,
                dict[str, object],
                dict[str, object],
                ExecutionRequest,
            ],
            bool,
        ]
        | None
    ) = None
    failure_handler: Callable[..., None] | None = None
