"""Profile-based conventions that replace repo-bound defaults."""

from pydantic import BaseModel, Field

from vibe3.models.branch_convention import BranchConvention


class ProfileConvention(BaseModel):
    """Profile-based conventions that replace repo-bound defaults.

    All convention fields have sensible defaults for minimal profile,
    but can be overridden by repo config or profile selection.

    The model is frozen (immutable) to ensure convention consistency
    throughout the application lifecycle.
    """

    model_config = {"frozen": True}

    branch: BranchConvention = Field(
        default_factory=BranchConvention.minimal, description="Branch naming convention"
    )

    state_prefix: str = Field(
        default="state/",
        description="Prefix for state labels (empty string = no prefix)",
    )

    handoff_label: str = Field(
        default="handoff",
        description="Label for handoff state (without state_prefix)",
    )

    blocked_label: str = Field(
        default="blocked",
        description="Label for blocked state (without state_prefix)",
    )

    manager_usernames: list[str] = Field(
        default_factory=lambda: [],
        description="GitHub usernames for manager dispatch (empty = disabled)",
    )

    supervisor_prompt: str = Field(
        default="orchestra.supervisor.apply",
        description="Dotted prompt path for supervisor execution",
    )

    @classmethod
    def vibe_center(cls) -> "ProfileConvention":
        """Vibe Center opinionated defaults."""
        return cls(
            branch=BranchConvention.vibe_center(),
            state_prefix="state/",
            handoff_label="handoff",
            blocked_label="blocked",
            manager_usernames=["vibe-manager-agent"],
            supervisor_prompt="orchestra.supervisor.apply",
        )

    def state_label(self, state: str) -> str:
        """Return full state label with prefix.

        Args:
            state: State name without prefix (e.g., "handoff", "blocked")

        Returns:
            Full label (e.g., "state/handoff" or "handoff" if prefix disabled)
        """
        return f"{self.state_prefix}{state}"
