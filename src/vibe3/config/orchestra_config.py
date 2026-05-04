"""Orchestra configuration models.

These configuration classes are shared across orchestra, manager, and agents
modules. Moved to config layer to fix architecture violation (config should
not depend on models).
"""

import subprocess
from pathlib import Path

from loguru import logger
from pydantic import BaseModel, Field


def _default_pid_file() -> Path:
    """Resolve PID path under shared git common dir when available."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if result.returncode == 0:
            git_common_dir = result.stdout.strip()
            if git_common_dir:
                common_path = Path(git_common_dir)
                if not common_path.is_absolute():
                    common_path = (Path.cwd() / common_path).resolve()
                return common_path / "vibe3" / "orchestra.pid"
    except Exception:
        logger.bind(domain="orchestra").debug(
            "Cannot resolve git common dir, using default PID path"
        )
    return Path(".git/vibe3/orchestra.pid")


class CommentReplyConfig(BaseModel):
    """Configuration for the comment reply service."""

    enabled: bool = True


class PollingConfig(BaseModel):
    """Configuration for heartbeat polling fallback."""

    enabled: bool = True


class AssigneeDispatchConfig(BaseModel):
    """Configuration for assignee-based manager dispatch."""

    enabled: bool = True
    use_worktree: bool = True
    agent: str | None = None
    backend: str | None = None
    model: str | None = None
    timeout_seconds: int = Field(
        default=3600,
        ge=60,
        description="Manager execution timeout in seconds (default 60 minutes)",
    )
    prompt_template: str = Field(
        default="orchestra.assignee_dispatch.manager",
        description="Dotted prompts.yaml path used to render the manager task prompt",
    )
    token_env: str | None = Field(
        default="VIBE_MANAGER_GITHUB_TOKEN",
        description=(
            "Environment variable name for manager-specific GitHub token. "
            "If set and the env var exists, its value will be injected into "
            "ExecutionRequest.env['GH_TOKEN'], enabling role isolation. "
            "If None or the env var is not set, falls back to global GH_TOKEN."
        ),
    )


class PRReviewDispatchConfig(BaseModel):
    """Configuration for PR review dispatch service."""

    enabled: bool = True
    async_mode: bool = True
    use_worktree: bool = False


class StateLabelDispatchConfig(BaseModel):
    """Configuration for state/ready label-based manager dispatch."""

    enabled: bool = True


class CircuitBreakerConfig(BaseModel):
    """Configuration for dispatch-level circuit breaker."""

    enabled: bool = True
    failure_threshold: int = Field(
        default=4,
        ge=1,
        description="Consecutive failures to trigger OPEN",
    )
    cooldown_seconds: int = Field(
        default=300,
        ge=60,
        description="Duration of OPEN state",
    )
    half_open_max_tests: int = Field(
        default=1, ge=1, description="Test requests allowed in HALF_OPEN"
    )


class GovernanceConfig(BaseModel):
    """Configuration for periodic governance scan service."""

    enabled: bool = True
    supervisor_file: str = Field(
        default="supervisor/governance/assignee-pool.md",
        description=(
            "Supervisor material source for governance prompt assembly. "
            "Prompt templates decide whether this material is rendered."
        ),
    )
    supervisor_files: list[str] = Field(
        default=[],
        description="Multiple governance material files for round-robin rotation. "
        "Takes precedence over supervisor_file when non-empty.",
    )

    def get_supervisor_materials(self) -> list[str]:
        """Return the list of governance material files to rotate through.

        supervisor_files takes precedence; falls back to [supervisor_file].
        """
        if self.supervisor_files:
            return list(self.supervisor_files)
        return [self.supervisor_file]

    prompt_template: str = Field(
        default="orchestra.governance.plan",
        description="Dotted prompts.yaml path used to render governance prompt",
    )
    dry_run: bool = False
    interval_ticks: int = Field(
        default=4,
        ge=1,
        description=(
            "Run governance scan every N heartbeat ticks (~1h at default interval)"
        ),
    )
    agent: str | None = Field(
        default=None,
        description="Agent preset name for governance execution",
    )
    backend: str | None = Field(
        default=None,
        description=(
            "Backend override (leave empty to use config/v3/models.json preset)"
        ),
    )
    model: str | None = Field(
        default=None,
        description="Model override (leave empty to use config/v3/models.json preset)",
    )


class SupervisorHandoffConfig(BaseModel):
    """Configuration for supervisor handoff issue consumption."""

    enabled: bool = True
    issue_label: str = "supervisor"
    handoff_state_label: str = "state/handoff"
    interval_ticks: int = Field(
        default=4,
        description="Run supervisor scan every N heartbeat ticks (same as governance)",
    )
    prompt_template: str = Field(
        default="orchestra.supervisor.apply",
        description="Dotted prompts.yaml path used to render supervisor/apply prompt",
    )
    agent: str | None = Field(
        default=None,
        description="Agent preset name for supervisor handoff execution",
    )
    backend: str | None = Field(
        default=None,
        description=(
            "Backend override (leave empty to use config/v3/models.json preset)"
        ),
    )
    model: str | None = Field(
        default=None,
        description="Model override (leave empty to use config/v3/models.json preset)",
    )


class WorktreeCleanupConfig(BaseModel):
    """Configuration for temporary worktree cleanup (do/* worktrees)."""

    enabled: bool = True
    ttl_hours: int = Field(default=72, ge=1)
    on_pr_closed: bool = True
    dry_run: bool = False


class OrchestraConfig(BaseModel):
    """Orchestra daemon configuration.

    Shared configuration model for orchestra, manager, and agents modules.
    Moved to config layer to fix architecture violation.
    """

    enabled: bool = True
    polling_interval: int = Field(default=900, ge=1)
    debug_polling_interval: int = Field(default=60, ge=1)
    debug_max_ticks: int = Field(default=10, ge=1)
    debug: bool = False
    scene_base_ref: str = Field(default="origin/main", min_length=1)
    repo: str | None = None
    max_concurrent_flows: int = Field(default=3, ge=1)
    async_execution: bool = Field(
        default=True,
        description=(
            "If True, manager dispatch runs via tmux (non-blocking). "
            "If False, runs synchronously (blocking, for debugging)."
        ),
    )

    # Per-role capacity configuration
    governance_max_concurrent: int = Field(
        default=1,
        ge=1,
        description="Maximum concurrent governance executions",
    )
    supervisor_max_concurrent: int = Field(
        default=2,
        ge=1,
        description="Maximum concurrent supervisor executions",
    )

    dry_run: bool = False
    pid_file: Path = Field(default_factory=_default_pid_file)
    port: int = Field(default=8080, ge=1, le=65535)
    webhook_secret: str | None = None
    bot_username: str | None = Field(
        default=None,
        description=(
            "The GitHub username of the bot itself, used to avoid self-triggering loops"
        ),
    )
    manager_usernames: list[str] = Field(
        default_factory=lambda: ["vibe-manager-agent"],
        description="GitHub usernames whose assignment signals manager dispatch",
    )
    polling: PollingConfig = Field(default_factory=PollingConfig)
    assignee_dispatch: AssigneeDispatchConfig = Field(
        default_factory=AssigneeDispatchConfig
    )
    comment_reply: CommentReplyConfig = Field(default_factory=CommentReplyConfig)
    pr_review_dispatch: PRReviewDispatchConfig = Field(
        default_factory=PRReviewDispatchConfig
    )
    state_label_dispatch: StateLabelDispatchConfig = Field(
        default_factory=StateLabelDispatchConfig
    )
    circuit_breaker: CircuitBreakerConfig = Field(default_factory=CircuitBreakerConfig)
    governance: GovernanceConfig = Field(default_factory=GovernanceConfig)
    supervisor_handoff: SupervisorHandoffConfig = Field(
        default_factory=SupervisorHandoffConfig
    )
    cleanup: WorktreeCleanupConfig = Field(default_factory=WorktreeCleanupConfig)
