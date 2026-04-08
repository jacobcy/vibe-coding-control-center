"""Supervisor apply domain events.

Events for supervisor handoff service (L2 execution chain).

This is an independent chain from the main L3 agent chain
(Manager/Plan/Run/Review). Supervisor + Apply handles lightweight
governance execution with temporary worktree isolation.

Reference: docs/standards/vibe3-worktree-ownership-standard.md §二 (L2)
"""

from dataclasses import dataclass

# Import base class from parent module
from vibe3.domain.events import DomainEvent as _DomainEvent

# Re-export for convenience
DomainEvent = _DomainEvent


@dataclass(frozen=True)
class SupervisorIssueIdentified(DomainEvent):
    """Supervisor issue identified event.

    Published when supervisor handoff service detects an issue
    with supervisor+state/handoff labels.
    """

    issue_number: int
    issue_title: str
    supervisor_file: str
    actor: str = "system:supervisor"
    timestamp: str | None = None


@dataclass(frozen=True)
class SupervisorPromptRendered(DomainEvent):
    """Supervisor prompt rendered event.

    Published when supervisor prompt is successfully rendered
    from governance service.
    """

    issue_number: int
    supervisor_file: str
    prompt_length: int
    actor: str = "system:supervisor"
    timestamp: str | None = None


@dataclass(frozen=True)
class SupervisorApplyDispatched(DomainEvent):
    """Supervisor apply dispatched event.

    Published when supervisor handoff service dispatches
    an apply agent to process a governance issue.

    Note: Uses temporary worktree isolation (--worktree flag).
    """

    issue_number: int
    tmux_session: str
    supervisor_file: str
    actor: str = "agent:supervisor"
    timestamp: str | None = None


@dataclass(frozen=True)
class SupervisorApplyStarted(DomainEvent):
    """Supervisor apply started event.

    Published when apply agent begins execution in its
    temporary worktree.
    """

    issue_number: int
    worktree_path: str
    supervisor_file: str
    actor: str = "agent:apply"
    timestamp: str | None = None


@dataclass(frozen=True)
class SupervisorApplyCompleted(DomainEvent):
    """Supervisor apply completed event.

    Published when apply agent finishes processing a governance issue.

    Possible outcomes:
    - Label changes (state transitions)
    - Comments added
    - Issue closed
    - Simple doc/config fixes
    - Complex changes → new task issue created (delegated to L3)
    """

    issue_number: int
    supervisor_file: str
    outcome: str  # "success", "delegated", "partial", "failed"
    actions_taken: list[
        str
    ]  # e.g., ["updated_labels", "added_comment", "closed_issue"]
    actor: str = "agent:apply"
    timestamp: str | None = None


@dataclass(frozen=True)
class SupervisorApplyDelegated(DomainEvent):
    """Supervisor apply delegated event.

    Published when apply agent determines the issue requires
    complex code changes beyond L2 scope.

    Action: Creates a formal task issue with spec for L3 manager chain.
    """

    governance_issue_number: int
    new_task_issue_number: int
    reason: str
    actor: str = "agent:apply"
    timestamp: str | None = None
