"""Governance role definition."""

from vibe3.execution.role_contracts import GOVERNANCE_GATE_CONFIG
from vibe3.roles.definitions import RoleDefinition

GOVERNANCE_ROLE = RoleDefinition(
    name="governance",
    registry_role="governance",
    gate_config=GOVERNANCE_GATE_CONFIG,
)
