"""Check cleanup configuration models."""

from pydantic import BaseModel, Field


class CheckCleanupSettings(BaseModel):
    """Check cleanup configuration for expired resource cleanup."""

    agent_worktree_max_age_days: int = Field(
        default=7, ge=1, description="Max age in days for agent worktrees"
    )
    remote_branch_max_age_days: int = Field(
        default=7, ge=1, description="Max age in days for remote branches"
    )
    local_branch_max_age_days: int = Field(
        default=7, ge=1, description="Max age in days for local branches"
    )
    enable_agent_worktree_cleanup: bool = Field(
        default=True, description="Enable agent worktree cleanup"
    )
    enable_remote_branch_cleanup: bool = Field(
        default=True, description="Enable remote branch cleanup"
    )
    enable_local_branch_cleanup: bool = Field(
        default=True, description="Enable local branch cleanup"
    )
    protected_worktree_names: list[str] = Field(
        default_factory=lambda: [
            "main",
            "develop",
            "wt-develop",
            "claude",
            "wt-claude",
            "codex",
            "wt-codex",
        ],
        description=(
            "Worktree directory names (or name prefixes) that are never deleted. "
            "A worktree is protected when its basename exactly matches or starts "
            "with one of these names followed by '-' or '_'."
        ),
    )
