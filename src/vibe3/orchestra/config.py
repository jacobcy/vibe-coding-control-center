"""Orchestra configuration."""

import subprocess
from pathlib import Path

from loguru import logger
from pydantic import BaseModel, Field

from vibe3.agents.review_runner import AgentOptions


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
    prompt_template: str = Field(
        default="orchestra.assignee_dispatch.manager",
        description="Dotted prompts.yaml path used to render the manager task prompt",
    )
    skill: str | None = Field(
        default="vibe-manager",
        description="Skill to include in manager prompt (None disables skill content)",
    )
    include_skill_content: bool = Field(
        default=False,
        description="Whether to inline the skill body into the manager prompt",
    )


class PRReviewDispatchConfig(BaseModel):
    """Configuration for PR review dispatch service."""

    enabled: bool = True
    async_mode: bool = False
    use_worktree: bool = False


class MasterAgentConfig(BaseModel):
    """Master agent configuration."""

    enabled: bool = True
    agent: str = "master-controller"
    backend: str | None = None
    model: str | None = None
    timeout_seconds: int = 300

    def to_agent_options(self) -> AgentOptions:
        return AgentOptions(
            agent=self.agent,
            backend=self.backend,
            model=self.model,
            timeout_seconds=self.timeout_seconds,
        )


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
    skill: str = Field(
        default="vibe-orchestra",
        description="Governance skill material to include in the composed prompt",
    )
    prompt_template: str = Field(
        default="orchestra.governance.plan",
        description="Dotted prompts.yaml path used to render governance prompt",
    )
    include_skill_content: bool = Field(
        default=True,
        description="Whether to inline the governance skill body into the prompt",
    )
    dry_run: bool = False
    interval_ticks: int = Field(
        default=4,
        ge=1,
        description=(
            "Run governance scan every N heartbeat ticks (~1h at default interval)"
        ),
    )


class OrchestraConfig(BaseModel):
    """Orchestra daemon configuration."""

    enabled: bool = True
    polling_interval: int = Field(default=900, ge=60)
    repo: str | None = None
    max_concurrent_flows: int = Field(default=3, ge=1)
    dry_run: bool = False
    pid_file: Path = Field(default_factory=_default_pid_file)
    port: int = Field(default=8080, ge=1, le=65535)
    webhook_secret: str | None = None
    manager_usernames: list[str] = Field(
        default_factory=lambda: ["vibe-manager-agent"],
        description="GitHub usernames whose assignment signals manager dispatch",
    )
    master_agent: MasterAgentConfig = Field(default_factory=MasterAgentConfig)
    polling: PollingConfig = Field(default_factory=PollingConfig)
    assignee_dispatch: AssigneeDispatchConfig = Field(
        default_factory=AssigneeDispatchConfig
    )
    comment_reply: CommentReplyConfig = Field(default_factory=CommentReplyConfig)
    pr_review_dispatch: PRReviewDispatchConfig = Field(
        default_factory=PRReviewDispatchConfig
    )
    circuit_breaker: CircuitBreakerConfig = Field(default_factory=CircuitBreakerConfig)
    governance: GovernanceConfig = Field(default_factory=GovernanceConfig)

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

        governance_defaults: dict[str, bool | str | int] = {
            "enabled": True,
            "skill": "vibe-orchestra",
            "prompt_template": "orchestra.governance.plan",
            "include_skill_content": True,
            "dry_run": False,
            "interval_ticks": 4,
        }
        governance_src = getattr(src, "governance", None)
        if governance_src is not None:
            if isinstance(governance_src, dict):
                governance_defaults.update(governance_src)
            else:
                governance_defaults.update(
                    {
                        "enabled": getattr(governance_src, "enabled", True),
                        "skill": getattr(governance_src, "skill", "vibe-orchestra"),
                        "prompt_template": getattr(
                            governance_src,
                            "prompt_template",
                            "orchestra.governance.plan",
                        ),
                        "include_skill_content": getattr(
                            governance_src, "include_skill_content", True
                        ),
                        "dry_run": getattr(governance_src, "dry_run", False),
                        "interval_ticks": getattr(governance_src, "interval_ticks", 4),
                    }
                )

        return cls(
            enabled=src.enabled,
            polling_interval=src.polling_interval,
            repo=repo,
            max_concurrent_flows=src.max_concurrent_flows,
            port=src.port,
            webhook_secret=src.webhook_secret,
            manager_usernames=src.manager_usernames,
            master_agent=MasterAgentConfig(
                enabled=src.master_agent.enabled,
                agent=src.master_agent.agent,
                backend=src.master_agent.backend,
                model=src.master_agent.model,
                timeout_seconds=src.master_agent.timeout_seconds,
            ),
            polling=PollingConfig(enabled=src.polling.enabled),
            assignee_dispatch=AssigneeDispatchConfig(
                enabled=src.assignee_dispatch.enabled,
                use_worktree=src.assignee_dispatch.use_worktree,
                prompt_template=getattr(
                    src.assignee_dispatch,
                    "prompt_template",
                    "orchestra.assignee_dispatch.manager",
                ),
                skill=getattr(src.assignee_dispatch, "skill", "vibe-manager"),
                include_skill_content=getattr(
                    src.assignee_dispatch, "include_skill_content", False
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
            circuit_breaker=circuit_breaker_config,
            governance=GovernanceConfig.model_validate(governance_defaults),
        )
