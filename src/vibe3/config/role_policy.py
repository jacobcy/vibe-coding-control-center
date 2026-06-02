"""Centralized role policy mapping for execution roles.

This module provides a single source of truth for role-specific policies,
eliminating scattered mappings across multiple modules.
"""

from typing import Literal

from vibe3.roles.definitions import RoleOutputContract

# Role to config section mapping
# Note: Uses str instead of ExecutionRole because it includes "manager"
# which is not part of ExecutionRole (only planner/executor/reviewer)
ROLE_TO_SECTION: dict[str, Literal["manager", "plan", "run", "review"]] = {
    "manager": "manager",
    "planner": "plan",
    "executor": "run",
    "reviewer": "review",
}


def get_role_section(role: str) -> Literal["manager", "plan", "run", "review"]:
    """Get the config section for a given role."""
    return ROLE_TO_SECTION[role]


# Role output contracts for the unified no-op gate.
# Mirrors the output_contract field on each role's TriggerableRoleDefinition,
# kept here as a separate lookup so noop_gate can resolve contracts by role
# name string without importing from roles/ (which would create a cycle via
# roles/plan.py → execution/codeagent_runner.py → execution/noop_gate.py).
ROLE_OUTPUT_CONTRACTS: dict[str, RoleOutputContract] = {
    "planner": RoleOutputContract(required_ref="plan_ref"),
    "executor": RoleOutputContract(),
    "reviewer": RoleOutputContract(requires_verdict=True),
    "manager": RoleOutputContract(),
}


def get_role_output_contract(role: str) -> RoleOutputContract:
    """Return the output contract for a given role name.

    Falls back to an empty contract (no requirements) for unknown roles.
    """
    return ROLE_OUTPUT_CONTRACTS.get(role, RoleOutputContract())
