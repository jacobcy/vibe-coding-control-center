"""PR data models."""

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field

from vibe3.services.signature_service import SignatureService


class PRState(str, Enum):
    """PR state."""

    OPEN = "OPEN"
    CLOSED = "CLOSED"
    MERGED = "MERGED"
    DRAFT = "DRAFT"


class PRMetadata(BaseModel):
    """PR metadata for vibe3 integration."""

    branch: Optional[str] = Field(None, description="Branch name (primary identifier)")
    task_issue: Optional[int] = Field(None, description="Task issue number")
    flow_slug: Optional[str] = Field(None, description="Flow slug (display name)")
    spec_ref: Optional[str] = Field(None, description="Spec reference path")
    planner: Optional[str] = Field(None, description="Planner agent")
    executor: Optional[str] = Field(None, description="Executor agent")
    reviewer: Optional[str] = Field(None, description="Reviewer agent")
    latest: Optional[str] = Field(None, description="Latest actor")

    @property
    def contributors(self) -> list[str]:
        """Return normalized, deduplicated list of non-placeholder actors.

        Source fields: planner, executor, reviewer, latest.
        Dedup is by backend (part before ``/``) so that ``Agent-Claude``
        and ``claude/sonnet-4.6`` merge into a single entry.  When the
        same backend appears multiple times, the most specific form
        (the one containing a model) wins.

        Fallback: If all actors are placeholders, use git worktree user.name
        to ensure the Contributors block always exists (per authorship standard).
        """
        backend_map: dict[str, str] = {}
        field_order: list[str] = []

        for raw in (self.planner, self.executor, self.reviewer, self.latest):
            normalized = SignatureService.normalize_actor(raw) if raw else None
            if not normalized:
                continue
            backend = normalized.split("/")[0]
            if backend not in backend_map:
                field_order.append(backend)
                backend_map[backend] = normalized
            elif "/" in normalized and "/" not in backend_map[backend]:
                backend_map[backend] = normalized

        # Fallback to worktree user.name if all actors are placeholders
        if not backend_map:
            from vibe3.clients.git_client import GitClient

            try:
                worktree_actor = GitClient().get_config("user.name")
                if worktree_actor:
                    normalized = SignatureService.normalize_actor(worktree_actor)
                    if normalized:
                        return [normalized]
            except Exception:
                pass
            # Ultimate fallback if git config unavailable
            return ["human"]

        return [backend_map[b] for b in field_order]


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
    ci_status: Optional[str] = Field(None, description="Raw CI status rollup")
    created_at: Optional[datetime] = Field(None, description="Created at")
    updated_at: Optional[datetime] = Field(None, description="Updated at")
    merged_at: Optional[datetime] = Field(None, description="Merged at")
    metadata: Optional[PRMetadata] = Field(None, description="PR metadata")
    comments: list[dict[str, Any]] = Field(default_factory=list)
    review_comments: list[dict[str, Any]] = Field(default_factory=list)


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
