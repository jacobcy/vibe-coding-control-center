"""PR data models."""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class PRState(str, Enum):
    """PR state."""

    OPEN = "OPEN"
    CLOSED = "CLOSED"
    MERGED = "MERGED"
    DRAFT = "DRAFT"


class PRMetadata(BaseModel):
    """PR metadata for vibe3 integration."""

    task_issue: Optional[int] = Field(None, description="Task issue number")
    flow_slug: Optional[str] = Field(None, description="Flow slug")
    spec_ref: Optional[str] = Field(None, description="Spec reference path")
    planner: Optional[str] = Field(None, description="Planner agent")
    executor: Optional[str] = Field(None, description="Executor agent")


class CreatePRRequest(BaseModel):
    """Request model for creating PR."""

    title: str = Field(..., description="PR title")
    body: str = Field(..., description="PR body/description")
    head_branch: str = Field(..., description="Head branch name")
    base_branch: str = Field("main", description="Base branch name")
    draft: bool = Field(True, description="Create as draft PR")
    metadata: Optional[PRMetadata] = Field(None, description="PR metadata")


class PRResponse(BaseModel):
    """Response model for PR operations."""

    number: int = Field(..., description="PR number")
    title: str = Field(..., description="PR title")
    body: str = Field("", description="PR body/description")
    state: PRState = Field(..., description="PR state")
    head_branch: str = Field(..., description="Head branch name")
    base_branch: str = Field(..., description="Base branch name")
    url: str = Field(..., description="PR URL")
    draft: bool = Field(False, description="Is draft PR")
    is_ready: bool = Field(False, description="Is ready for review (not draft)")
    ci_passed: bool = Field(False, description="CI checks passed")
    created_at: Optional[datetime] = Field(None, description="Created at")
    updated_at: Optional[datetime] = Field(None, description="Updated at")
    merged_at: Optional[datetime] = Field(None, description="Merged at")
    metadata: Optional[PRMetadata] = Field(None, description="PR metadata")


class UpdatePRRequest(BaseModel):
    """Request model for updating PR."""

    number: int = Field(..., description="PR number")
    title: Optional[str] = Field(None, description="PR title")
    body: Optional[str] = Field(None, description="PR body/description")
    draft: Optional[bool] = Field(None, description="Draft status")
    base_branch: Optional[str] = Field(None, description="Base branch name")


class VersionBumpType(str, Enum):
    """Version bump type."""

    PATCH = "patch"
    MINOR = "minor"
    MAJOR = "major"
    NONE = "none"


class VersionBumpRequest(BaseModel):
    """Request model for version bump calculation."""

    pr_number: int = Field(..., description="PR number")
    group: Optional[str] = Field(
        None, description="Task group (feature/bug/docs/chore)"
    )


class VersionBumpResponse(BaseModel):
    """Response model for version bump."""

    current_version: str = Field(..., description="Current version")
    bump_type: VersionBumpType = Field(..., description="Bump type")
    next_version: str = Field(..., description="Next version")
    reason: str = Field(..., description="Reason for bump type")


class ReviewRequest(BaseModel):
    """Request model for PR review."""

    pr_number: int = Field(..., description="PR number")
    local: bool = Field(False, description="Use local LLM (codex)")
    publish: bool = Field(True, description="Publish review as comment")


class ReviewResponse(BaseModel):
    """Response model for PR review."""

    pr_number: int = Field(..., description="PR number")
    review_body: str = Field(..., description="Review content")
    published: bool = Field(False, description="Whether review was published")
