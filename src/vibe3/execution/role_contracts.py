"""Role dispatch contracts for unified role execution.

This module defines the contracts that make role-specific logic explicit
and decouple role handlers from execution framework details.
"""

from dataclasses import dataclass
from enum import Enum


class WorktreeRequirement(str, Enum):
    """Worktree requirement for a role execution."""

    NONE = "none"  # No worktree needed (governance)
    PERMANENT = "permanent"  # Permanent worktree (manager)
    TEMPORARY = "temporary"  # Temporary worktree (supervisor apply)


class CompletionContract(str, Enum):
    """How to judge if a role execution is valid."""

    MUST_CHANGE_LABEL = "must_change_label"  # Manager: must not be no-op
    MAY_COMMENT_OR_PROPOSE = (
        "may_comment_or_propose"  # Governance: no label change required
    )
    APPLY_OR_PARTIAL = (
        "apply_or_partial"  # Supervisor apply: apply/partial/delegated/failed
    )


@dataclass
class RoleGateConfig:
    """Configuration for role-specific gates.

    These are the policy differences between roles, extracted to make
    role behavior explicit rather than hidden in role-specific code.
    """

    worktree: WorktreeRequirement = WorktreeRequirement.NONE
    completion_contract: CompletionContract = CompletionContract.MAY_COMMENT_OR_PROPOSE
    requires_flow: bool = False  # Whether role needs flow/scene
    requires_issue: bool = False  # Whether role needs issue context


# Role-specific gate configurations
MANAGER_GATE_CONFIG = RoleGateConfig(
    worktree=WorktreeRequirement.PERMANENT,
    completion_contract=CompletionContract.MUST_CHANGE_LABEL,
    requires_flow=True,
    requires_issue=True,
)

GOVERNANCE_GATE_CONFIG = RoleGateConfig(
    worktree=WorktreeRequirement.NONE,
    completion_contract=CompletionContract.MAY_COMMENT_OR_PROPOSE,
    requires_flow=False,
    requires_issue=False,
)

PLANNER_GATE_CONFIG = RoleGateConfig(
    worktree=WorktreeRequirement.PERMANENT,
    completion_contract=CompletionContract.MAY_COMMENT_OR_PROPOSE,
    requires_flow=True,
    requires_issue=True,
)

EXECUTOR_GATE_CONFIG = RoleGateConfig(
    worktree=WorktreeRequirement.PERMANENT,
    completion_contract=CompletionContract.MAY_COMMENT_OR_PROPOSE,
    requires_flow=True,
    requires_issue=True,
)

REVIEWER_GATE_CONFIG = RoleGateConfig(
    worktree=WorktreeRequirement.PERMANENT,
    completion_contract=CompletionContract.MAY_COMMENT_OR_PROPOSE,
    requires_flow=True,
    requires_issue=True,
)

SUPERVISOR_IDENTIFY_GATE_CONFIG = RoleGateConfig(
    worktree=WorktreeRequirement.NONE,
    completion_contract=CompletionContract.MAY_COMMENT_OR_PROPOSE,
    requires_flow=False,
    requires_issue=True,
)

SUPERVISOR_APPLY_GATE_CONFIG = RoleGateConfig(
    worktree=WorktreeRequirement.TEMPORARY,
    completion_contract=CompletionContract.APPLY_OR_PARTIAL,
    requires_flow=False,
    requires_issue=True,
)
