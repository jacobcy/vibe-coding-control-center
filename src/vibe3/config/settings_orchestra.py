"""Orchestra daemon configuration models."""

from pydantic import BaseModel, Field


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
    agent: str = "develop"
    backend: str | None = None
    model: str | None = None
    prompt_template: str = "orchestra.assignee_dispatch.manager"
    supervisor_file: str | None = "supervisor/manager.md"
    include_supervisor_content: bool = True


class OrchestraPRReviewDispatchSettings(BaseModel):
    """PR review dispatch settings for orchestra."""

    enabled: bool = True
    async_mode: bool = False
    use_worktree: bool = False


class OrchestraStateLabelDispatchSettings(BaseModel):
    """Settings for state/ready label-driven dispatch."""

    enabled: bool = True


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
    supervisor_file: str = "supervisor/orchestra.md"
    prompt_template: str = "orchestra.governance.plan"
    include_supervisor_content: bool = True
    dry_run: bool = False
    agent: str = "explore"
    backend: str | None = None
    model: str | None = None


class OrchestraSupervisorHandoffSettings(BaseModel):
    """Supervisor handoff issue consumer settings."""

    enabled: bool = True
    issue_label: str = "supervisor"
    handoff_state_label: str = "state/handoff"
    supervisor_file: str = "supervisor/apply.md"
    agent: str = "explore"
    backend: str | None = None
    model: str | None = None


class OrchestraSettings(BaseModel):
    """Orchestra daemon settings."""

    enabled: bool = True
    polling_interval: int = 900
    debug_polling_interval: int = 60
    scene_base_ref: str = "origin/main"
    port: int = 8080
    webhook_secret: str | None = None
    bot_username: str | None = None
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
    state_label_dispatch: OrchestraStateLabelDispatchSettings = Field(
        default_factory=OrchestraStateLabelDispatchSettings
    )
    circuit_breaker: OrchestraCircuitBreakerSettings = Field(
        default_factory=OrchestraCircuitBreakerSettings
    )
    governance: OrchestraGovernanceSettings = Field(
        default_factory=OrchestraGovernanceSettings
    )
    supervisor_handoff: OrchestraSupervisorHandoffSettings = Field(
        default_factory=OrchestraSupervisorHandoffSettings
    )
