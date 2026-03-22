"""Flow and Task data models."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class FlowState(BaseModel):
    """Flow state model."""

    branch: str
    flow_slug: str
    task_issue_number: int | None = None
    pr_number: int | None = None
    spec_ref: str | None = None
    plan_ref: str | None = None
    report_ref: str | None = None
    audit_ref: str | None = None
    planner_actor: str | None = None
    planner_session_id: str | None = None
    executor_actor: str | None = None
    executor_session_id: str | None = None
    reviewer_actor: str | None = None
    reviewer_session_id: str | None = None
    latest_actor: str | None = None
    blocked_by: str | None = None
    next_step: str | None = None
    flow_status: Literal["active", "blocked", "done", "stale"] = "active"
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())

    @field_validator("flow_status", mode="before")
    @classmethod
    def migrate_flow_status(cls, v: str) -> str:
        """Migrate legacy flow status values.

        - idle -> active (default state)
        - missing -> stale (inactive state)
        """
        if v == "idle":
            return "active"
        if v == "missing":
            return "stale"
        return v


class IssueLink(BaseModel):
    """Issue link model."""

    branch: str
    issue_number: int
    issue_role: Literal["task", "repo"]
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())

    @field_validator("issue_role", mode="before")
    @classmethod
    def migrate_issue_role(cls, v: str) -> str:
        """Migrate legacy issue role values.

        - related -> repo (repository-scoped role)
        """
        if v == "related":
            return "repo"
        return v


class FlowEvent(BaseModel):
    """Flow event model."""

    id: int | None = None
    branch: str
    event_type: str
    actor: str
    detail: str | None = None
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class CreateFlowRequest(BaseModel):
    """Request model for creating a flow."""

    slug: str
    branch: str
    task_id: str | None = None


class FlowStatusResponse(BaseModel):
    """Response model for flow status."""

    branch: str
    flow_slug: str
    flow_status: Literal["active", "blocked", "done", "stale"]
    task_issue_number: int | None = None
    pr_number: int | None = None
    spec_ref: str | None = None
    next_step: str | None = None
    issues: list[IssueLink] = Field(default_factory=list)
