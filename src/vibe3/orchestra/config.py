"""Orchestra configuration."""

import subprocess
from pathlib import Path

from loguru import logger
from pydantic import BaseModel, Field

from vibe3.services.review_runner import AgentOptions


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
        default_factory=lambda: ["vibe-manager"],
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

    @classmethod
    def from_settings(cls) -> "OrchestraConfig":
        """Load config from settings.yaml via OrchestraSettings."""
        from vibe3.config.settings import VibeConfig

        settings = VibeConfig.get_defaults()
        src = settings.orchestra

        repo = src.repo
        if isinstance(repo, str):
            repo = repo.strip() or None

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
            ),
            comment_reply=CommentReplyConfig(
                enabled=src.comment_reply.enabled,
            ),
            pr_review_dispatch=PRReviewDispatchConfig(
                enabled=src.pr_review_dispatch.enabled,
                async_mode=src.pr_review_dispatch.async_mode,
                use_worktree=src.pr_review_dispatch.use_worktree,
            ),
        )
