"""Orchestra configuration."""

import subprocess
from pathlib import Path

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
        pass
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

        comment_reply_cfg = getattr(orchestra_config, "comment_reply", None)
        comment_reply = CommentReplyConfig()
        if comment_reply_cfg:
            comment_reply = CommentReplyConfig(
                enabled=getattr(comment_reply_cfg, "enabled", True),
            )

        polling_cfg = getattr(orchestra_config, "polling", None)
        polling = PollingConfig()
        if polling_cfg:
            polling = PollingConfig(
                enabled=getattr(polling_cfg, "enabled", True),
            )

        assignee_dispatch_cfg = getattr(orchestra_config, "assignee_dispatch", None)
        assignee_dispatch = AssigneeDispatchConfig()
        if assignee_dispatch_cfg:
            assignee_dispatch = AssigneeDispatchConfig(
                enabled=getattr(assignee_dispatch_cfg, "enabled", True),
                use_worktree=getattr(assignee_dispatch_cfg, "use_worktree", True),
            )

        pr_review_cfg = getattr(orchestra_config, "pr_review_dispatch", None)
        pr_review_dispatch = PRReviewDispatchConfig()
        if pr_review_cfg:
            pr_review_dispatch = PRReviewDispatchConfig(
                enabled=getattr(pr_review_cfg, "enabled", True),
                async_mode=getattr(pr_review_cfg, "async_mode", False),
                use_worktree=getattr(pr_review_cfg, "use_worktree", False),
            )

        repo = getattr(orchestra_config, "repo", None)
        if isinstance(repo, str):
            repo = repo.strip() or None

        return cls(
            enabled=getattr(orchestra_config, "enabled", True),
            polling_interval=getattr(orchestra_config, "polling_interval", 900),
            repo=repo,
            max_concurrent_flows=getattr(orchestra_config, "max_concurrent_flows", 3),
            port=getattr(orchestra_config, "port", 8080),
            webhook_secret=getattr(orchestra_config, "webhook_secret", None),
            manager_usernames=getattr(
                orchestra_config, "manager_usernames", ["vibe-manager"]
            ),
            master_agent=master_agent,
            polling=polling,
            assignee_dispatch=assignee_dispatch,
            comment_reply=comment_reply,
            pr_review_dispatch=pr_review_dispatch,
        )
