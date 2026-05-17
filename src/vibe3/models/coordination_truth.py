"""Coordination truth table model for remote-first reads."""

from pydantic import BaseModel, Field

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

    # Combined state
    is_blocked: bool = Field(
        default=False,
        description="Blocked state inferred from blocked_reason + blocked_by_issue",
    )

    def model_post_init(self, __context: object) -> None:
        """Compute is_blocked from blocked_reason and blocked_by_issue."""
        self.is_blocked = bool(self.blocked_reason or self.blocked_by_issue)
