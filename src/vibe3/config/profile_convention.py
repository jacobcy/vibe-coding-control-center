"""Profile-based conventions that replace repo-bound defaults."""

from pydantic import BaseModel, Field

from vibe3.models import BranchConvention


class LabelsConvention(BaseModel):
    """Labels convention for state and task labels.

    Groups all label-related configuration in one place for easier access.
    The model is frozen (immutable) to ensure convention consistency.
    """

    model_config = {"frozen": True}

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

    vibe_task: str = Field(
        default="vibe-task",
        description="Label for vibe-task identification",
    )

    manager_usernames: tuple[str, ...] = Field(
        default_factory=tuple,
        description="GitHub usernames for manager dispatch (empty = disabled)",
    )

    @classmethod
    def minimal(cls) -> "LabelsConvention":
        """Minimal defaults for portable/minimal profile."""
        return cls(
            state_prefix="state/",
            handoff_label="handoff",
            blocked_label="blocked",
            vibe_task="vibe-task",
            manager_usernames=(),
        )

    @classmethod
    def vibe_center(cls) -> "LabelsConvention":
        """Vibe Center opinionated defaults."""
        return cls(
            state_prefix="state/",
            handoff_label="handoff",
            blocked_label="blocked",
            vibe_task="vibe-task",
            manager_usernames=("vibe-manager-agent",),
        )


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

    vibe_task: str = Field(
        default="vibe-task",
        description="Label for vibe-task identification",
    )

    manager_usernames: tuple[str, ...] = Field(
        default_factory=tuple,
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
            vibe_task="vibe-task",
            manager_usernames=("vibe-manager-agent",),
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

    @property
    def labels(self) -> LabelsConvention:
        """Return LabelsConvention grouping all label-related fields.

        Returns:
            LabelsConvention instance with current label configuration
        """
        return LabelsConvention(
            state_prefix=self.state_prefix,
            handoff_label=self.handoff_label,
            blocked_label=self.blocked_label,
            vibe_task=self.vibe_task,
            manager_usernames=self.manager_usernames,
        )
