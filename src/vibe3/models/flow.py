"""Flow and Task data models."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class MainBranchProtectedError(Exception):
    """Cannot create flow on protected main branches.

    Main branches (main, master, develop, etc.) are protected and cannot
    have flows. Flows are only for feature branches.
    """

    pass


ExecutionStatus = Literal["pending", "running", "done", "crashed"]


def _migrate_flow_status_value(v: str) -> str:
    """Normalize legacy flow status values."""
    if v == "idle":
        return "active"
    if v == "missing":
        return "stale"
    if v == "merged":
        return "done"
    return v


class FlowState(BaseModel):
    """Flow state model.

    Session tracking is now handled by runtime_session registry.
    Legacy session_id fields (manager_session_id, planner_session_id,
    executor_session_id, reviewer_session_id) are no longer in the model.
    """

    branch: str
    flow_slug: str
    spec_ref: str | None = None
    plan_ref: str | None = None
    report_ref: str | None = None
    audit_ref: str | None = None
    pr_ref: str | None = None  # PR URL as proof of PR creation
    planner_actor: str | None = None
    executor_actor: str | None = None
    reviewer_actor: str | None = None
    latest_actor: str | None = None
    initiated_by: str | None = None
    blocked_by: str | None = (
        None  # Legacy field (deprecated, kept for backward compatibility)
    )
    blocked_by_issue: int | None = (
        None  # NEW: Dependency issue number (semantic clarity)
    )
    blocked_reason: str | None = None  # NEW: Block reason text (semantic clarity)
    failed_reason: str | None = None  # NEW: Fail reason text
    next_step: str | None = None
    flow_status: Literal[
        "active", "blocked", "failed", "done", "stale", "aborted", "merged"
    ] = "active"

    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    planner_status: ExecutionStatus | None = None
    executor_status: ExecutionStatus | None = None
    reviewer_status: ExecutionStatus | None = None
    execution_pid: int | None = None
    execution_started_at: str | None = None
    execution_completed_at: str | None = None

    model_config = {"extra": "ignore"}

    @field_validator("flow_status", mode="before")
    @classmethod
    def migrate_flow_status(cls, v: str) -> str:
        """Migrate legacy flow status values.

        - idle -> active (default state)
        - missing -> stale (inactive state)
        - merged -> done (completed state)
        """
        return _migrate_flow_status_value(v)


class IssueLink(BaseModel):
    """Issue link model."""

    branch: str
    issue_number: int
    issue_role: Literal["task", "related", "dependency"]
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())

    @field_validator("issue_role", mode="before")
    @classmethod
    def migrate_issue_role(cls, v: str) -> str:
        """Migrate legacy issue role values.

        - repo -> related (legacy classification -> relation semantics)
        """
        if v == "repo":
            return "related"
        return v

    @staticmethod
    def resolve_task_number(
        links: list["IssueLink"] | list[dict],
    ) -> int | None:
        """Resolve the primary task issue number from links.

        Truth: any issue with 'task' role.
        """
        for link in links:
            role = link.get("issue_role") if isinstance(link, dict) else link.issue_role
            if role == "task":
                return (
                    link.get("issue_number")
                    if isinstance(link, dict)
                    else link.issue_number
                )
        return None


class FlowEvent(BaseModel):
    id: int | None = None
    branch: str
    event_type: str
    actor: str
    detail: str | None = None
    refs: dict[str, str | list[str]] | None = None
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())

    @field_validator("refs", mode="before")
    @classmethod
    def normalize_refs(
        cls, v: dict[str, object] | None
    ) -> dict[str, str | list[str]] | None:
        """Normalize legacy event refs loaded from SQLite.

        Older events may store bool/int values. Timeline rendering only needs
        display-safe strings (or lists of strings), so coerce scalars here
        instead of failing on historical data.
        """
        if v is None:
            return None
        normalized: dict[str, str | list[str]] = {}
        for key, value in v.items():
            if isinstance(value, list):
                normalized[key] = [str(item) for item in value]
            elif value is None:
                continue
            else:
                normalized[key] = str(value)
        return normalized


class FlowStatusResponse(BaseModel):
    """Response model for flow status.

    Session tracking is now handled by runtime_session registry.
    Legacy session_id fields are no longer included.
    """

    branch: str
    flow_slug: str
    flow_status: Literal[
        "active", "blocked", "failed", "done", "stale", "aborted", "merged"
    ]
    task_issue_number: int | None = None
    pr_number: int | None = None
    pr_ready_for_review: bool = False
    spec_ref: str | None = None
    plan_ref: str | None = None
    report_ref: str | None = None
    audit_ref: str | None = None
    planner_actor: str | None = None
    executor_actor: str | None = None
    reviewer_actor: str | None = None
    latest_actor: str | None = None
    initiated_by: str | None = None
    blocked_by: str | None = None  # Legacy field (deprecated)
    blocked_by_issue: int | None = None  # NEW: Dependency issue number
    blocked_reason: str | None = None  # NEW: Block reason text
    failed_reason: str | None = None  # NEW: Fail reason text
    next_step: str | None = None
    issues: list[IssueLink] = Field(default_factory=list)
    planner_status: ExecutionStatus | None = None
    executor_status: ExecutionStatus | None = None
    reviewer_status: ExecutionStatus | None = None
    execution_pid: int | None = None
    execution_started_at: str | None = None
    execution_completed_at: str | None = None

    @field_validator("flow_status", mode="before")
    @classmethod
    def migrate_flow_status(cls, v: str) -> str:
        """Migrate legacy flow status values for status responses."""
        return _migrate_flow_status_value(v)

    @classmethod
    def from_state(
        cls,
        state: FlowState | dict,
        issues: list[IssueLink] | None = None,
        pr_number: int | None = None,
        pr_ready: bool | None = None,
    ) -> "FlowStatusResponse":
        """Build a hydrated response from state and links."""
        data = state.model_dump() if isinstance(state, FlowState) else dict(state)
        issues = issues or []

        # Truth-only: resolve task issue number from links
        resolved_task_issue_number = IssueLink.resolve_task_number(issues)

        return cls(
            branch=data["branch"],
            flow_slug=data["flow_slug"],
            flow_status=data.get("flow_status", "active"),
            task_issue_number=resolved_task_issue_number,
            pr_number=pr_number if pr_number is not None else data.get("pr_number"),
            pr_ready_for_review=(
                pr_ready
                if pr_ready is not None
                else bool(data.get("pr_ready_for_review"))
            ),
            spec_ref=data.get("spec_ref"),
            plan_ref=data.get("plan_ref"),
            report_ref=data.get("report_ref"),
            audit_ref=data.get("audit_ref"),
            planner_actor=data.get("planner_actor"),
            executor_actor=data.get("executor_actor"),
            reviewer_actor=data.get("reviewer_actor"),
            latest_actor=data.get("latest_actor"),
            initiated_by=data.get("initiated_by"),
            blocked_by=data.get("blocked_by"),
            blocked_by_issue=data.get("blocked_by_issue"),
            blocked_reason=data.get("blocked_reason"),
            failed_reason=data.get("failed_reason"),
            next_step=data.get("next_step"),
            issues=issues,
            planner_status=data.get("planner_status"),
            executor_status=data.get("executor_status"),
            reviewer_status=data.get("reviewer_status"),
            execution_pid=data.get("execution_pid"),
            execution_started_at=data.get("execution_started_at"),
            execution_completed_at=data.get("execution_completed_at"),
        )


class CreateDecision(BaseModel):
    """Decision model for flow create operation."""

    allowed: bool
    reason: str
    start_ref: str | None = None
    allow_base_current: bool = False
    requires_new_worktree: bool = False
    guidance: str | None = None


class CloseTargetDecision(BaseModel):
    """Decision model for flow close target branch."""

    target_branch: str
    should_pull: bool
    reason: str
