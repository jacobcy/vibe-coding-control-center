"""Orchestra configuration."""

from pathlib import Path

from pydantic import BaseModel, Field

from vibe3.models.orchestration import IssueState


class StateTrigger(BaseModel):
    """Trigger configuration for a state transition."""

    from_state: IssueState | None
    to_state: IssueState
    command: str
    args: list[str] = Field(default_factory=list)


STATE_TRIGGERS: list[StateTrigger] = [
    StateTrigger(
        from_state=IssueState.READY,
        to_state=IssueState.CLAIMED,
        command="plan",
        args=["execute"],
    ),
    StateTrigger(
        from_state=IssueState.CLAIMED,
        to_state=IssueState.IN_PROGRESS,
        command="run",
        args=["execute"],
    ),
    StateTrigger(
        from_state=IssueState.IN_PROGRESS,
        to_state=IssueState.REVIEW,
        command="review",
        args=["pr"],
    ),
]


class OrchestraConfig(BaseModel):
    """Orchestra daemon configuration."""

    enabled: bool = True
    polling_interval: int = Field(default=60, ge=30)
    repo: str | None = None
    max_concurrent_flows: int = Field(default=3, ge=1)
    dry_run: bool = False
    pid_file: Path = Field(default=Path(".git/vibe/orchestra.pid"))

    @classmethod
    def from_settings(cls) -> "OrchestraConfig":
        """Load config from settings.yaml."""
        from vibe3.config.settings import VibeConfig

        config = VibeConfig.get_defaults()
        orchestra_config = getattr(config, "orchestra", None)

        if orchestra_config:
            return cls(
                enabled=getattr(orchestra_config, "enabled", True),
                polling_interval=getattr(orchestra_config, "polling_interval", 60),
                repo=getattr(orchestra_config, "repo", None),
                max_concurrent_flows=getattr(
                    orchestra_config, "max_concurrent_flows", 3
                ),
            )
        return cls()
