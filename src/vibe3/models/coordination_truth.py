"""Coordination truth table model for remote-first reads."""

from typing import Self

from pydantic import BaseModel, Field, model_validator

from vibe3.models.data_source import DataSource


class CoordinationTruth(BaseModel):
    """Remote-first coordination state with provenance.

    Truth table for orchestra/qualify coordination reads:
    - Collaboration fields: remote-first (issue body > local DB)
    - Execution fields: local-first (local DB only)
    """

    # Collaboration fields (remote-first)
    blocked_reason: str | None = Field(
        default=None,
        description="Block reason from issue body or local DB",
    )
    blocked_reason_source: DataSource | None = Field(
        default=None,
        description="Provenance: ISSUE_BODY_FALLBACK or LOCAL_SQLITE",
    )

    blocked_by_issue: int | None = Field(
        default=None,
        description="Blocking issue number from issue body or local DB",
    )
    blocked_by_issue_source: DataSource | None = Field(
        default=None,
        description="Provenance: ISSUE_BODY_FALLBACK or LOCAL_SQLITE",
    )

    dependencies: list[int] = Field(
        default_factory=list,
        description="Dependency issue numbers from issue body or local DB",
    )
    dependencies_source: DataSource | None = Field(
        default=None,
        description="Provenance: ISSUE_BODY_FALLBACK or LOCAL_SQLITE",
    )

    # Execution fields (local-only)
    worktree_path: str | None = Field(
        default=None,
        description="Worktree path from local DB only",
    )
    actor: str | None = Field(
        default=None,
        description="Latest actor from local DB only",
    )

    @model_validator(mode="after")
    def validate_source_consistency(self) -> Self:
        """Ensure source fields are set when corresponding values are provided."""
        if self.blocked_reason is not None and self.blocked_reason_source is None:
            raise ValueError(
                "blocked_reason_source must be set when blocked_reason is provided"
            )
        if self.blocked_by_issue is not None and self.blocked_by_issue_source is None:
            raise ValueError(
                "blocked_by_issue_source must be set when blocked_by_issue is provided"
            )
        if self.dependencies and self.dependencies_source is None:
            raise ValueError(
                "dependencies_source must be set when dependencies are provided"
            )
        return self

    @property
    def is_blocked(self) -> bool:
        """Compute blocked state from blocked_reason and blocked_by_issue."""
        return bool(self.blocked_reason or self.blocked_by_issue)
