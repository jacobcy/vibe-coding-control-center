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
    handoff_state_label: str = Field(
        default="",
        description=(
            "State label for handoff (e.g., 'state/handoff'). "
            "Empty string uses ConventionResolver to resolve from profile."
        ),
    )
    interval_ticks: int = Field(
        default=4,
        description="Run supervisor scan every N heartbeat ticks (same as governance)",
    )
    prompt_template: str = Field(
        default="",
        description=(
            "Dotted prompts.yaml path used to render supervisor/apply prompt. "
            "Empty string uses ConventionResolver to resolve from profile."
        ),
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

    def get_handoff_state_label(self) -> str:
        """Resolve handoff state label with fallback to ConventionResolver.

        Returns:
            Handoff state label (e.g., 'state/handoff').

        Example:
            >>> config = SupervisorHandoffConfig()
            >>> config.get_handoff_state_label()
            'state/handoff'
        """
        if self.handoff_state_label:
            return self.handoff_state_label
        from vibe3.services.convention_resolver import ConventionResolver

        resolver = ConventionResolver.from_repo()
        convention = resolver.resolve()
        return convention.state_label(convention.handoff_label)


class PeriodicCheckConfig(BaseModel):
    """Configuration for periodic consistency checks via vibe3 check.

    Runs two phases on each interval tick:
    1. Consistency check: PR merged/closed, issue closed, multi-label detection
    2. Resource cleanup: expired worktrees and branches (if enabled)

    Cleanup is performed by calling execute_expired_resource_cleanup directly
    with the configuration flags below.
    """

    enabled: bool = True
    interval_ticks: int = Field(
        default=10,
        ge=1,
        description="Run check every N heartbeat ticks (~2.5h at default interval)",
    )
    max_age_days: int = Field(
        default=7, ge=1, description="Max age in days before cleanup"
    )
    enable_worktree_cleanup: bool = True
    enable_local_branch_cleanup: bool = True
    enable_remote_branch_cleanup: bool = True


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
    port_range_max: int | None = Field(
        default=None,
        ge=1,
        le=65535,
        description=(
            "Maximum port for auto-discovery range. "
            "If None, port must be available (no auto-discovery, backward-compatible). "
            "If set, enables auto-discovery from port to port_range_max."
        ),
    )
    bot_username: str | None = Field(
        default=None,
        description=(
            "The GitHub username of the bot itself, used to avoid self-triggering loops"
        ),
    )
    manager_usernames: tuple[str, ...] = Field(
        default_factory=tuple,
        description=(
            "GitHub usernames whose assignment signals manager dispatch. "
            "Empty tuple uses ConventionResolver to resolve from profile."
        ),
    )
    polling: PollingConfig = Field(default_factory=PollingConfig)
    assignee_dispatch: AssigneeDispatchConfig = Field(
        default_factory=AssigneeDispatchConfig
    )
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
    periodic_check: PeriodicCheckConfig = Field(default_factory=PeriodicCheckConfig)
    max_retry_budget: int = Field(
        default=3,
        ge=1,
        description=(
            "Max re-dispatch attempts for a queue entry whose issue state "
            "remains unchanged"
        ),
    )

    def get_manager_usernames(self) -> tuple[str, ...]:
        """Resolve manager usernames with fallback to ConventionResolver.

        Returns:
            Tuple of manager usernames (e.g., ('vibe-manager-agent',)).

        Example:
            >>> config = OrchestraConfig()
            >>> config.get_manager_usernames()
            ('vibe-manager-agent',)
        """
        if self.manager_usernames:
            return self.manager_usernames
        from vibe3.services.convention_resolver import ConventionResolver

        resolver = ConventionResolver.from_repo()
        convention = resolver.resolve()
        return convention.manager_usernames

    def get_supervisor_prompt(self) -> str:
        """Resolve supervisor prompt template with fallback to ConventionResolver.

        Returns:
            Dotted prompt template path (e.g., 'orchestra.supervisor.apply').

        Example:
            >>> config = OrchestraConfig()
            >>> config.get_supervisor_prompt()
            'orchestra.supervisor.apply'
        """
        if self.supervisor_handoff.prompt_template:
            return self.supervisor_handoff.prompt_template
        from vibe3.services.convention_resolver import ConventionResolver

        resolver = ConventionResolver.from_repo()
        convention = resolver.resolve()
        return convention.supervisor_prompt
