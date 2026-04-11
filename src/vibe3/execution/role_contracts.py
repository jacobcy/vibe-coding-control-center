"""Role dispatch contracts for unified role execution.

This module defines the contracts that make role-specific logic explicit
and decouple role handlers from execution framework details.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Literal, Optional


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


@dataclass
class RoleDispatchRequest:
    """Unified request to dispatch a role execution.

    This captures the truly variable parts of role execution, making
    role handlers focus on building these payloads instead of managing
    the entire execution framework.

    Attributes:
        role: Role name (manager/governance/supervisor)
        target_id: Issue number or tick count
        target_branch: Branch name or identifier
        execution_name: Unique execution name for logging
        cwd: Working directory (worktree path for manager/supervisor)
        prompt: Prompt text (for agent-based roles)
        options: Agent options
        cmd: Command to run (for command-based roles)
        refs: Additional references (task, session_id, etc.)
        env: Environment variables
        actor: Who initiated this execution
        mode: sync or async execution
        gate_config: Role-specific gate configuration
    """

    role: str
    target_id: int
    target_branch: str
    execution_name: str
    cwd: Optional[str] = None
    prompt: Optional[str] = None
    options: Optional[Any] = None
    cmd: Optional[List[str]] = None
    refs: Dict[str, str] = field(default_factory=dict)
    env: Optional[Dict[str, str]] = None
    actor: str = "orchestra:system"
    mode: Literal["sync", "async"] = "async"
    gate_config: RoleGateConfig = field(default_factory=RoleGateConfig)


@dataclass
class RoleGateResult:
    """Result of a gate check.

    Gates are pre-execution checks that validate role-specific requirements
    before dispatching execution.
    """

    allowed: bool
    reason: Optional[str] = None
    reason_code: Optional[str] = None


@dataclass
class RoleCompletionPolicy:
    """Policy for judging role execution completion.

    Different roles have different standards for what constitutes a
    successful execution. This makes those standards explicit.
    """

    contract: CompletionContract

    def is_valid_completion(self, result: Any) -> bool:
        """Check if execution result satisfies the completion contract.

        Args:
            result: Execution result to validate

        Returns:
            True if the result satisfies the contract
        """
        if self.contract == CompletionContract.MAY_COMMENT_OR_PROPOSE:
            # Governance: any result is valid (can comment/propose without changes)
            return True
        elif self.contract == CompletionContract.MUST_CHANGE_LABEL:
            # Manager: must have actual changes (no-op is failure)
            if hasattr(result, "changed") and hasattr(result, "changed_labels"):
                return result.changed or len(result.changed_labels) > 0
            return False
        elif self.contract == CompletionContract.APPLY_OR_PARTIAL:
            # Supervisor apply: must be one of the valid outcomes
            if hasattr(result, "status"):
                return result.status in ("apply", "partial", "delegated", "failed")
            return False
        return True


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
