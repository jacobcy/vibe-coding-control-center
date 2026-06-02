"""Centralized role policy mapping for execution roles.

This module provides a single source of truth for role-specific policies,
eliminating scattered mappings across multiple modules.

NOTE: This module MUST remain free of vibe3 imports to avoid circular
imports. The import chain roles/definitions.py → execution/contracts.py →
execution/__init__.py → codeagent_runner.py → config/role_policy.py must
not loop back into roles/.
"""

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class RoleOutputContract:
    """Declarative contract for what a role must produce after execution.

    Used by the unified no-op gate to validate post-execution outputs.
    Each role declares its own contract in its TriggerableRoleDefinition.

    Attributes:
        required_ref: flow_state key that must be non-empty after execution.
            Gate blocks if the key is absent or empty, regardless of whether
            the state label changed. None means no ref is required.
        requires_verdict: If True, flow_state["latest_verdict"] must be set.
            Used exclusively by the reviewer role.
    """

    required_ref: str | None = None
    requires_verdict: bool = False


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
