"""Supervisor role definitions."""

from vibe3.execution.role_contracts import (
    SUPERVISOR_APPLY_GATE_CONFIG,
    SUPERVISOR_IDENTIFY_GATE_CONFIG,
)
from vibe3.roles.definitions import RoleDefinition

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
