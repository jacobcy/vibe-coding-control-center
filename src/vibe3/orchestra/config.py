"""Orchestra configuration."""

from pathlib import Path

from pydantic import BaseModel, Field

from vibe3.models.orchestration import IssueState
from vibe3.services.review_runner import ReviewAgentOptions


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
        args=["task"],
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


class MasterAgentConfig(BaseModel):
    """Master agent configuration."""

    enabled: bool = True
    agent: str = "master-controller"
    backend: str | None = None
    model: str | None = None
    timeout_seconds: int = 300

    def to_agent_options(self) -> ReviewAgentOptions:
        return ReviewAgentOptions(
            agent=self.agent,
            backend=self.backend,
            model=self.model,
            timeout_seconds=self.timeout_seconds,
        )


class OrchestraConfig(BaseModel):
    """Orchestra daemon configuration."""

    enabled: bool = True
    polling_interval: int = Field(default=60, ge=30)
    repo: str | None = None
    max_concurrent_flows: int = Field(default=3, ge=1)
    dry_run: bool = False
    pid_file: Path = Field(default=Path(".git/vibe/orchestra.pid"))
    master_agent: MasterAgentConfig = Field(default_factory=MasterAgentConfig)

    @classmethod
    def from_settings(cls) -> "OrchestraConfig":
        """Load config from settings.yaml."""
        from vibe3.config.settings import VibeConfig

        config = VibeConfig.get_defaults()
        orchestra_config = getattr(config, "orchestra", None)

        if not orchestra_config:
            return cls()

        master_cfg = getattr(orchestra_config, "master_agent", None)
        master_agent = MasterAgentConfig()
        if master_cfg:
            master_agent = MasterAgentConfig(
                enabled=getattr(master_cfg, "enabled", True),
                agent=getattr(master_cfg, "agent", "master-controller"),
                backend=getattr(master_cfg, "backend", None),
                model=getattr(master_cfg, "model", None),
                timeout_seconds=getattr(master_cfg, "timeout_seconds", 300),
            )

        return cls(
            enabled=getattr(orchestra_config, "enabled", True),
            polling_interval=getattr(orchestra_config, "polling_interval", 60),
            repo=getattr(orchestra_config, "repo", None),
            max_concurrent_flows=getattr(orchestra_config, "max_concurrent_flows", 3),
            master_agent=master_agent,
        )
