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


@dataclass(frozen=True)
class IssueResolvedDependency(DomainEvent):
    """Published when a closed issue may resolve dependency blockers.

    Signals that downstream flows blocked by this issue may need
    re-evaluation. Consumers must use the observer-only auto eligibility
    API (see #3289 / #3292) and must NOT invoke
    BlockedStateService.reconcile_blocked or infer a dispatchable target
    from local refs (plan_ref/pr_ref/report_ref/audit_ref).
    """

    issue_number: int
    merged: bool
    pr_number: int | None = None
    actor: str = "system:dispatch"
    timestamp: str | None = None


@dataclass(frozen=True)
class ManualPlanIntent(DomainEvent):
    """Published when CLI plan command is invoked."""

    issue_number: int | None
    branch: str
    request: object = None  # PlanRequest (frozen dataclass)
    dry_run: bool = False
    no_async: bool = False
    show_prompt: bool = False
    agent: str | None = None
    backend: str | None = None
    model: str | None = None
    fresh_session: bool = False
    actor: str = "cli:plan"
    timestamp: str | None = None


@dataclass(frozen=True)
class FlowBlocked(DomainEvent):
    """Published when a flow enters blocked state."""

    issue_number: int
    branch: str
    blocked_reason: str
    actor: str = "system:flow"
    timestamp: str | None = None


@dataclass(frozen=True)
class ManualRunIntent(DomainEvent):
    """Published when CLI run command is invoked."""

    issue_number: int | None
    branch: str
    instructions: str | None = None
    plan_file: str | None = None
    skill: str | None = None
    summary_mode: str = "plan"
    summary_message: str | None = None
    summary_branch: str | None = None
    dry_run: bool = False
    no_async: bool = False
    show_prompt: bool = False
    agent: str | None = None
    backend: str | None = None
    model: str | None = None
    fresh_session: bool = False
    publish: bool = False
    actor: str = "cli:run"
    timestamp: str | None = None


@dataclass(frozen=True)
class FlowCompleted(DomainEvent):
    """Published when a flow is marked done."""

    issue_number: int
    branch: str
    completed_state: str  # "done" | "merged"
    actor: str = "system:flow"
    timestamp: str | None = None


@dataclass(frozen=True)
class ManualReviewIntent(DomainEvent):
    """Published when CLI review command is invoked."""

    issue_number: int | None
    branch: str
    is_base_review: bool = False
    request: object = None  # ReviewRequest (frozen dataclass)
    instructions: str | None = None
    dry_run: bool = False
    no_async: bool = False
    show_prompt: bool = False
    agent: str | None = None
    backend: str | None = None
    model: str | None = None
    fresh_session: bool = False
    actor: str = "cli:review"
    timestamp: str | None = None


@dataclass(frozen=True)
class PRMerged(DomainEvent):
    """Published when a PR merge is detected."""

    issue_number: int
    branch: str
    pr_number: int
    merged_by: str | None = None
    actor: str = "system:check"
    timestamp: str | None = None


@dataclass(frozen=True)
class PolicyChanged(DomainEvent):
    """Published when policy configuration files change."""

    changed_files: tuple[str, ...]
    scope: tuple[str, ...] = ()
    actor: str = "system:policy"
    timestamp: str | None = None


@dataclass(frozen=True)
class ControlPlaneEventPublished(DomainEvent):
    """Published as audit record when the control-plane API mutates state."""

    event_type: str  # Name of the DomainEvent that was published
    issue_number: int | None = None
    actor: str = "control-plane"
    source: str = "unknown"  # e.g. "web-dashboard", "api-client"
    idempotency_key: str = ""
    detail: str = ""
    timestamp: str | None = None
