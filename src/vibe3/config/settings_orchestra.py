"""Orchestra daemon configuration models."""

from pydantic import BaseModel, Field


class MasterAgentSettings(BaseModel):
    """Master agent settings for issue triage."""

    enabled: bool = True
    agent: str = "master-controller"
    backend: str | None = None
    model: str | None = None
    timeout_seconds: int = 300


class OrchestraCommentReplySettings(BaseModel):
    """Comment reply settings for orchestra."""

    enabled: bool = True


class OrchestraPollingSettings(BaseModel):
    """Polling fallback settings for orchestra heartbeat."""

    enabled: bool = True


class OrchestraAssigneeDispatchSettings(BaseModel):
    """Assignee-driven orchestra dispatch settings."""

    enabled: bool = True
    use_worktree: bool = True
    prompt_template: str = "orchestra.assignee_dispatch.manager"
    skill: str | None = "vibe-manager"
    include_skill_content: bool = False


class OrchestraPRReviewDispatchSettings(BaseModel):
    """PR review dispatch settings for orchestra."""

    enabled: bool = True
    async_mode: bool = False
    use_worktree: bool = False


class OrchestraCircuitBreakerSettings(BaseModel):
    """Circuit breaker settings for orchestra dispatch."""

    enabled: bool = True
    failure_threshold: int = 3
    cooldown_seconds: int = 300
    half_open_max_tests: int = 1


class OrchestraGovernanceSettings(BaseModel):
    """Periodic governance scan settings."""

    enabled: bool = True
    interval_ticks: int = 4
    skill: str = "vibe-orchestra"
    prompt_template: str = "orchestra.governance.plan"
    include_skill_content: bool = True
    dry_run: bool = False


class OrchestraSettings(BaseModel):
    """Orchestra daemon settings."""

    enabled: bool = True
    polling_interval: int = 900
    port: int = 8080
    webhook_secret: str | None = None
    manager_usernames: list[str] = Field(default_factory=lambda: ["vibe-manager-agent"])
    repo: str | None = None
    max_concurrent_flows: int = 3
    polling: OrchestraPollingSettings = Field(default_factory=OrchestraPollingSettings)
    assignee_dispatch: OrchestraAssigneeDispatchSettings = Field(
        default_factory=OrchestraAssigneeDispatchSettings
    )
    comment_reply: OrchestraCommentReplySettings = Field(
        default_factory=OrchestraCommentReplySettings
    )
    pr_review_dispatch: OrchestraPRReviewDispatchSettings = Field(
        default_factory=OrchestraPRReviewDispatchSettings
    )
    master_agent: MasterAgentSettings = Field(default_factory=MasterAgentSettings)
    circuit_breaker: OrchestraCircuitBreakerSettings = Field(
        default_factory=OrchestraCircuitBreakerSettings
    )
    governance: OrchestraGovernanceSettings = Field(
        default_factory=OrchestraGovernanceSettings
    )
