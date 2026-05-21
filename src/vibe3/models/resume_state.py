"""Resume state model for source-aware operations."""

from pydantic import BaseModel, Field

from vibe3.models.data_source import DataSource


class ResumeState(BaseModel):
    """Resume state with source metadata."""

    issue_number: int
    branch: str | None = None
    blocked_by_issue: int | None = None
    blocked_reason: str | None = None
    assignee: str | None = None
    labels: list[str] = Field(default_factory=list)
    data_source: DataSource
