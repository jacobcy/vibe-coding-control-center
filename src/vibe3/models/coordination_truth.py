"""Coordination truth table model for remote-first reads."""

from typing import Self

from pydantic import BaseModel, Field, computed_field, model_validator

from vibe3.models.data_source import DataSource

# Blocked projection states that indicate truth
BLOCKED_PROJECTION_STATES: set[str] = {"blocked"}


class CoordinationTruth(BaseModel):
    """Remote-first coordination state with provenance.

    Truth table for orchestra/qualify coordination reads:
    - Collaboration fields: remote-first (issue body > local DB)
    - Execution fields: local-first (local DB only)
    """

    # Issue body projection state (remote-first)
    projection_state: str | None = Field(
        default=None,
        description="State: value from issue body projection",
    )
    projection_state_source: DataSource | None = Field(
        default=None,
        description="Provenance: ISSUE_BODY_FALLBACK or LOCAL_SQLITE",
    )

    # Collaboration fields (remote-first)
    blocked_reason: str | None = Field(
        default=None,
        description="Block reason from issue body or local DB",
    )
    blocked_reason_source: DataSource | None = Field(
        default=None,
        description="Provenance: ISSUE_BODY_FALLBACK or LOCAL_SQLITE",
    )

    blocked_by_issues: list[int] = Field(
        default_factory=list,
        description="Blocking issue numbers from issue body or local DB",
    )
    blocked_by_issue_source: DataSource | None = Field(
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
        if self.projection_state is not None and self.projection_state_source is None:
            raise ValueError(
                "projection_state_source must be set when projection_state is provided"
            )
        if self.blocked_reason is not None and self.blocked_reason_source is None:
            raise ValueError(
                "blocked_reason_source must be set when blocked_reason is provided"
            )
        if self.blocked_by_issues and self.blocked_by_issue_source is None:
            raise ValueError(
                "blocked_by_issue_source must be set when "
                "blocked_by_issues are provided"
            )

        return self

    @computed_field  # type: ignore[prop-decorator]
    @property
    def blocked_by_issue(self) -> int | None:
        """Backward compatibility: return first blocking issue if any."""
        return self.blocked_by_issues[0] if self.blocked_by_issues else None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_blocked(self) -> bool:
        """Compute blocked state from projection state and blocked payload.

        Remote blocked truth is defined as:
        - Explicit projection state is 'blocked', or
        - Blocked payload present (blocked_reason or blocked_by_issues)
        """
        if self.projection_state in BLOCKED_PROJECTION_STATES:
            return True
        return bool(self.blocked_reason or self.blocked_by_issues)
