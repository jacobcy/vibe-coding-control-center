"""Orchestra configuration."""

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
    agent: str = "develop"
    backend: str | None = None
    model: str | None = None
    prompt_template: str = Field(
        default="orchestra.assignee_dispatch.manager",
        description="Dotted prompts.yaml path used to render the manager task prompt",
    )
    supervisor_file: str | None = Field(
        default="supervisor/manager.md",
        description="Supervisor file to include in manager prompt (None disables)",
    )
    include_supervisor_content: bool = Field(
        default=True,
        description="Whether to include supervisor file content in the manager prompt",
    )


class PRReviewDispatchConfig(BaseModel):
    """Configuration for PR review dispatch service."""

    enabled: bool = True
    async_mode: bool = False
    use_worktree: bool = False


class StateLabelDispatchConfig(BaseModel):
    """Configuration for state/ready label-based manager dispatch."""

    enabled: bool = True


class CircuitBreakerConfig(BaseModel):
    """Configuration for dispatch-level circuit breaker."""

    enabled: bool = True
    failure_threshold: int = Field(
        default=3,
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
        default="supervisor/orchestra.md",
        description="Supervisor file to include in the composed governance prompt",
    )
    prompt_template: str = Field(
        default="orchestra.governance.plan",
        description="Dotted prompts.yaml path used to render governance prompt",
    )
    include_supervisor_content: bool = Field(
        default=True,
        description="Whether to inline the supervisor file content into the prompt",
    )
    dry_run: bool = False
    interval_ticks: int = Field(
        default=4,
        ge=1,
        description=(
            "Run governance scan every N heartbeat ticks (~1h at default interval)"
        ),
    )
    agent: str = Field(
        default="explore",
        description="Agent preset name for governance execution",
    )
    backend: str | None = Field(
        default=None,
        description="Backend override (leave empty to use config/models.json preset)",
    )
    model: str | None = Field(
        default=None,
        description="Model override (leave empty to use config/models.json preset)",
    )


class SupervisorHandoffConfig(BaseModel):
    """Configuration for supervisor handoff issue consumption."""

    enabled: bool = True
    issue_label: str = "supervisor"
    handoff_state_label: str = "state/handoff"
    supervisor_file: str = "supervisor/apply.md"
    agent: str = Field(
        default="explore",
        description="Agent preset name for supervisor handoff execution",
    )
    backend: str | None = Field(
        default=None,
        description="Backend override (leave empty to use config/models.json preset)",
    )
    model: str | None = Field(
        default=None,
        description="Model override (leave empty to use config/models.json preset)",
    )


class OrchestraConfig(BaseModel):
    """Orchestra daemon configuration."""

    enabled: bool = True
    polling_interval: int = Field(default=900, ge=1)
    debug_polling_interval: int = Field(default=60, ge=1)
    debug: bool = False
    scene_base_ref: str = Field(default="origin/main", min_length=1)
    repo: str | None = None
    max_concurrent_flows: int = Field(default=3, ge=1)
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

    @classmethod
    def from_settings(cls) -> "OrchestraConfig":
        """Load config from settings.yaml via OrchestraSettings."""
        from vibe3.config.settings import VibeConfig

        settings = VibeConfig.get_defaults()
        src = settings.orchestra

        repo = src.repo
        if isinstance(repo, str):
            repo = repo.strip() or None

        # Build circuit_breaker config with defaults
        circuit_breaker_config = CircuitBreakerConfig()
        if hasattr(src, "circuit_breaker") and src.circuit_breaker:
            cb = src.circuit_breaker
            circuit_breaker_config = CircuitBreakerConfig(
                enabled=getattr(cb, "enabled", True),
                failure_threshold=getattr(cb, "failure_threshold", 3),
                cooldown_seconds=getattr(cb, "cooldown_seconds", 300),
                half_open_max_tests=getattr(cb, "half_open_max_tests", 1),
            )

        governance_defaults: dict[str, bool | str | int | None] = {
            "enabled": True,
            "supervisor_file": "supervisor/orchestra.md",
            "prompt_template": "orchestra.governance.plan",
            "include_supervisor_content": True,
            "dry_run": False,
            "interval_ticks": 4,
            "agent": "explore",
            "backend": None,
            "model": None,
        }
        governance_src = getattr(src, "governance", None)
        if governance_src is not None:
            if isinstance(governance_src, dict):
                governance_defaults.update(governance_src)
            elif hasattr(governance_src, "__dict__"):
                # It's a settings object with attributes
                governance_defaults.update(
                    {
                        "enabled": getattr(governance_src, "enabled", True),
                        "supervisor_file": getattr(
                            governance_src,
                            "supervisor_file",
                            "supervisor/orchestra.md",
                        ),
                        "prompt_template": getattr(
                            governance_src,
                            "prompt_template",
                            "orchestra.governance.plan",
                        ),
                        "include_supervisor_content": getattr(
                            governance_src, "include_supervisor_content", True
                        ),
                        "dry_run": getattr(governance_src, "dry_run", False),
                        "interval_ticks": getattr(governance_src, "interval_ticks", 4),
                        "agent": getattr(governance_src, "agent", "explore"),
                        "backend": getattr(governance_src, "backend", None),
                        "model": getattr(governance_src, "model", None),
                    }
                )

        supervisor_handoff_defaults: dict[str, bool | str | None] = {
            "enabled": True,
            "issue_label": "supervisor",
            "handoff_state_label": "state/handoff",
            "supervisor_file": "supervisor/apply.md",
            "agent": "explore",
            "backend": None,
            "model": None,
        }
        supervisor_handoff_src = getattr(src, "supervisor_handoff", None)
        if supervisor_handoff_src is not None:
            if isinstance(supervisor_handoff_src, dict):
                supervisor_handoff_defaults.update(supervisor_handoff_src)
            elif hasattr(supervisor_handoff_src, "__dict__"):
                # It's a settings object with attributes
                supervisor_handoff_defaults.update(
                    {
                        "enabled": getattr(supervisor_handoff_src, "enabled", True),
                        "issue_label": getattr(
                            supervisor_handoff_src, "issue_label", "supervisor"
                        ),
                        "handoff_state_label": getattr(
                            supervisor_handoff_src,
                            "handoff_state_label",
                            "state/handoff",
                        ),
                        "supervisor_file": getattr(
                            supervisor_handoff_src,
                            "supervisor_file",
                            "supervisor/apply.md",
                        ),
                        "agent": getattr(supervisor_handoff_src, "agent", "explore"),
                        "backend": getattr(supervisor_handoff_src, "backend", None),
                        "model": getattr(supervisor_handoff_src, "model", None),
                    }
                )

        return cls(
            enabled=src.enabled,
            polling_interval=src.polling_interval,
            debug_polling_interval=getattr(src, "debug_polling_interval", 60),
            debug=False,
            scene_base_ref=getattr(src, "scene_base_ref", "origin/main"),
            repo=repo,
            max_concurrent_flows=src.max_concurrent_flows,
            port=src.port,
            webhook_secret=src.webhook_secret,
            bot_username=getattr(src, "bot_username", None),
            manager_usernames=src.manager_usernames,
            polling=PollingConfig(enabled=src.polling.enabled),
            assignee_dispatch=AssigneeDispatchConfig(
                enabled=src.assignee_dispatch.enabled,
                use_worktree=src.assignee_dispatch.use_worktree,
                agent=getattr(src.assignee_dispatch, "agent", "develop"),
                backend=getattr(src.assignee_dispatch, "backend", None),
                model=getattr(src.assignee_dispatch, "model", None),
                prompt_template=getattr(
                    src.assignee_dispatch,
                    "prompt_template",
                    "orchestra.assignee_dispatch.manager",
                ),
                supervisor_file=getattr(
                    src.assignee_dispatch, "supervisor_file", "supervisor/manager.md"
                ),
                include_supervisor_content=getattr(
                    src.assignee_dispatch, "include_supervisor_content", True
                ),
            ),
            comment_reply=CommentReplyConfig(
                enabled=src.comment_reply.enabled,
            ),
            pr_review_dispatch=PRReviewDispatchConfig(
                enabled=src.pr_review_dispatch.enabled,
                async_mode=src.pr_review_dispatch.async_mode,
                use_worktree=src.pr_review_dispatch.use_worktree,
            ),
            state_label_dispatch=StateLabelDispatchConfig(
                enabled=getattr(
                    getattr(src, "state_label_dispatch", None), "enabled", True
                )
            ),
            circuit_breaker=circuit_breaker_config,
            governance=GovernanceConfig.model_validate(governance_defaults),
            supervisor_handoff=SupervisorHandoffConfig.model_validate(
                supervisor_handoff_defaults
            ),
        )
