"""Declarative role definitions shared by runtime/domain/execution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from vibe3.execution.role_contracts import (
    GOVERNANCE_GATE_CONFIG,
    MANAGER_GATE_CONFIG,
    SUPERVISOR_APPLY_GATE_CONFIG,
    SUPERVISOR_IDENTIFY_GATE_CONFIG,
    RoleGateConfig,
)
from vibe3.models.orchestration import IssueState

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


MANAGER_ROLE = TriggerableRoleDefinition(
    name="manager",
    registry_role="manager",
    gate_config=MANAGER_GATE_CONFIG,
    trigger_name="manager",
    trigger_state=IssueState.READY,
)

HANDOFF_MANAGER_ROLE = TriggerableRoleDefinition(
    name="manager-handoff",
    registry_role="manager",
    gate_config=MANAGER_GATE_CONFIG,
    trigger_name="manager",
    trigger_state=IssueState.HANDOFF,
)

PLANNER_ROLE = TriggerableRoleDefinition(
    name="planner",
    registry_role="planner",
    gate_config=GOVERNANCE_GATE_CONFIG,
    trigger_name="plan",
    trigger_state=IssueState.CLAIMED,
)

EXECUTOR_ROLE = TriggerableRoleDefinition(
    name="executor",
    registry_role="executor",
    gate_config=GOVERNANCE_GATE_CONFIG,
    trigger_name="run",
    trigger_state=IssueState.IN_PROGRESS,
)

REVIEWER_ROLE = TriggerableRoleDefinition(
    name="reviewer",
    registry_role="reviewer",
    gate_config=GOVERNANCE_GATE_CONFIG,
    trigger_name="review",
    trigger_state=IssueState.REVIEW,
)

GOVERNANCE_ROLE = RoleDefinition(
    name="governance",
    registry_role="governance",
    gate_config=GOVERNANCE_GATE_CONFIG,
)

SUPERVISOR_IDENTIFY_ROLE = RoleDefinition(
    name="supervisor-identify",
    registry_role="supervisor",
    gate_config=SUPERVISOR_IDENTIFY_GATE_CONFIG,
)

SUPERVISOR_APPLY_ROLE = RoleDefinition(
    name="supervisor-apply",
    registry_role="supervisor",
    gate_config=SUPERVISOR_APPLY_GATE_CONFIG,
)

LABEL_DISPATCH_ROLES: tuple[TriggerableRoleDefinition, ...] = (
    MANAGER_ROLE,
    HANDOFF_MANAGER_ROLE,
    PLANNER_ROLE,
    EXECUTOR_ROLE,
    REVIEWER_ROLE,
)
