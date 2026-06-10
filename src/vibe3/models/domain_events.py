"""Domain events shared across orchestration layers.

Pure frozen dataclasses representing observable system events.
Defined here (models layer L6) rather than domain (L3) to break
the roles↔domain and execution↔domain circular dependencies.

Import directly from this module or via vibe3.models:
    from vibe3.models.domain_events import ManagerDispatchIntent
    from vibe3.models import ManagerDispatchIntent
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DomainEvent:
    """Base class for all domain events.

    Events are immutable (frozen) to ensure event integrity.
    """


@dataclass(frozen=True)
class IssueFailed(DomainEvent):
    """Published when a role (executor/planner/reviewer/manager) fails."""

    issue_number: int
    reason: str
    actor: str = "system"
    role: str | None = None
    timestamp: str | None = None


@dataclass(frozen=True)
class ManagerDispatchIntent(DomainEvent):
    """Authoritative signal that manager should be dispatched for an issue."""

    issue_number: int
    branch: str
    trigger_state: str  # "ready" | "handoff"
    issue_title: str | None = None
    actor: str = "orchestra:dispatcher"
    timestamp: str | None = None
    tick_id: int = 0


@dataclass(frozen=True)
class PlannerDispatchIntent(DomainEvent):
    """Authoritative signal that planner should be dispatched for an issue."""

    issue_number: int
    branch: str
    trigger_state: str  # "claimed"
    actor: str = "orchestra:dispatcher"
    timestamp: str | None = None
    tick_id: int = 0


@dataclass(frozen=True)
class ExecutorDispatchIntent(DomainEvent):
    """Authoritative signal that executor should be dispatched for an issue."""

    issue_number: int
    branch: str
    trigger_state: str  # "in-progress"
    actor: str = "orchestra:dispatcher"
    timestamp: str | None = None
    tick_id: int = 0


@dataclass(frozen=True)
class ReviewerDispatchIntent(DomainEvent):
    """Authoritative signal that reviewer should be dispatched for an issue."""

    issue_number: int
    branch: str
    trigger_state: str  # "review"
    actor: str = "orchestra:dispatcher"
    timestamp: str | None = None
    tick_id: int = 0


@dataclass(frozen=True)
class SupervisorIssueIdentified(DomainEvent):
    """Published when supervisor handoff service detects a governance issue."""

    issue_number: int
    issue_title: str
    supervisor_file: str
    actor: str = "system:supervisor"
    timestamp: str | None = None


@dataclass(frozen=True)
class WebhookLabelChanged(DomainEvent):
    """Published when a GitHub issue label is added or removed."""

    issue_number: int
    label: str
    action: str  # "labeled" | "unlabeled"
    sender: str = ""
    timestamp: str | None = None


@dataclass(frozen=True)
class WebhookIssueUpdated(DomainEvent):
    """Published when a GitHub issue is opened or edited."""

    issue_number: int
    action: str  # "opened" | "edited"
    sender: str = ""
    timestamp: str | None = None


@dataclass(frozen=True)
class WebhookPRMerged(DomainEvent):
    """Published when a GitHub pull request is merged."""

    pr_number: int
    branch: str = ""
    sender: str = ""
    timestamp: str | None = None


@dataclass(frozen=True)
class WebhookPRReviewed(DomainEvent):
    """Published when a GitHub PR review is submitted."""

    pr_number: int
    reviewer: str = ""
    state: str = ""  # "approved" | "changes_requested" | "commented"
    sender: str = ""
    timestamp: str | None = None


@dataclass(frozen=True)
class WebhookIssueClosed(DomainEvent):
    """Published when a GitHub issue is closed."""

    issue_number: int
    sender: str = ""
    timestamp: str | None = None
