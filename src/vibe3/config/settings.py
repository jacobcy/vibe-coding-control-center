"""Configuration models using pydantic for type safety.

配置真源原则：
- config/settings.yaml 是配置的真源
- Pydantic 模型只提供最小安全默认值（用于降级场景）
- 正常情况下所有配置都从 YAML 文件读取
"""

from pathlib import Path

from pydantic import BaseModel, Field

from vibe3.config.settings_pr import (
    FileChangeWeights,
    LineChangeWeights,
    MergeGateConfig,
    ModuleChangeWeights,
    PRScoringConfig,
    PRScoringThresholds,
    PRScoringWeights,
    SizeThreshold,
    SizeThresholds,
)


class AIConfig(BaseModel):
    """AI 辅助配置.

    用于 AI 辅助文案能力（如 pr create --ai）。
    """

    api_key_env: str = Field(default="DEEPSEEK_API_KEY")
    base_url: str = Field(default="https://api.deepseek.com/v1")
    model: str = Field(default="deepseek/deepseek-chat")
    timeout: int = Field(default=30, ge=1, le=300)


class FlowConfig(BaseModel):
    """Flow 管理配置."""

    protected_branches: list[str] = Field(
        default_factory=lambda: ["main", "master", "develop"],
        description="Branches that cannot have flows",
    )


__all__ = [
    "AIConfig",
    "FlowConfig",
    "PRScoringConfig",
    "MergeGateConfig",
    "PRScoringWeights",
    "PRScoringThresholds",
    "LineChangeWeights",
    "FileChangeWeights",
    "ModuleChangeWeights",
    "SizeThreshold",
    "SizeThresholds",
    "VibeConfig",
]


class SingleFileLocConfig(BaseModel):
    """单文件行数限制."""

    default: int = Field(default=200)
    max: int = Field(default=300)


class TotalFileLocConfig(BaseModel):
    """总行数限制."""

    v2_shell: int = Field(default=7000)
    v3_python: int = Field(default=9000)


class CodePathsConfig(BaseModel):
    v2_shell: list[str] = Field(default_factory=list)
    v3_python: list[str] = Field(default_factory=list)


class ScriptsPathsConfig(BaseModel):
    v2_shell: list[str] = Field(default_factory=list)
    v3_python: list[str] = Field(default_factory=list)


class TestPathsConfig(BaseModel):
    v2_shell: list[str] = Field(default_factory=list)
    v3_python: list[str] = Field(default_factory=list)


class CodeLimitsConfig(BaseModel):
    """代码量限制配置."""

    single_file_loc: SingleFileLocConfig = Field(default_factory=SingleFileLocConfig)
    total_file_loc: TotalFileLocConfig = Field(default_factory=TotalFileLocConfig)
    code_paths: CodePathsConfig = Field(default_factory=CodePathsConfig)
    scripts_paths: ScriptsPathsConfig = Field(default_factory=ScriptsPathsConfig)
    test_paths: TestPathsConfig = Field(default_factory=TestPathsConfig)


class ReviewScopeConfig(BaseModel):
    """Review scope configuration."""

    critical_paths: list[str] = Field(default_factory=list)
    public_api_paths: list[str] = Field(default_factory=list)


class AgentConfig(BaseModel):
    """Agent configuration for codeagent-wrapper.

    When using a preset (agent specified), backend/model can still be provided
    for database recording purposes. If backend is None, agent is passed to
    codeagent-wrapper as preset name. If backend is provided, it overrides
    the preset's backend/model.

    Actor resolution:
    - If backend is provided: use backend/model directly
    - If only agent is provided: use agent as identifier (preset name)
    """

    agent: str | None = Field(default=None)
    backend: str | None = Field(default=None)
    model: str | None = Field(default=None)


class ReviewConfig(BaseModel):
    """Review configuration."""

    policy_file: str = Field(default=".agent/rules/review-policy.md")
    common_rules: str = Field(default=".agent/rules/common.md")
    agent_config: AgentConfig = Field(default_factory=AgentConfig)
    output_format: str = Field(default="")
    review_task: str = Field(default="")
    review_prompt: str = Field(default="")


class PlanConfig(BaseModel):
    """Plan command configuration."""

    policy_file: str = Field(default=".agent/rules/plan-policy.md")
    common_rules: str = Field(default=".agent/rules/common.md")
    agent_config: AgentConfig = Field(default_factory=AgentConfig)
    output_format: str = Field(default="")
    plan_task: str = Field(default="")
    plan_prompt: str = Field(default="")


class RunConfig(BaseModel):
    """Run command configuration."""

    policy_file: str = Field(default=".agent/rules/run-policy.md")
    common_rules: str = Field(default=".agent/rules/common.md")
    agent_config: AgentConfig = Field(default_factory=AgentConfig)
    output_format: str = Field(default="")
    run_task: str = Field(default="")
    run_prompt: str = Field(default="")


class TestCoverageConfig(BaseModel):
    """Test coverage requirements."""

    services: int = Field(default=50, ge=0, le=100)
    clients: int = Field(default=50, ge=0, le=100)
    commands: int = Field(default=50, ge=0, le=100)


class QualityConfig(BaseModel):
    """Quality standards configuration."""

    test_coverage: TestCoverageConfig = Field(default_factory=TestCoverageConfig)


class GitHubProjectConfig(BaseModel):
    """GitHub Projects v2 配置。

    owner_type: "org" 或 "user"
    owner: GitHub 组织名或用户名
    project_number: GitHub Project number（URL 末尾的数字）
    """

    owner_type: str = Field(default="org")
    owner: str = Field(default="")
    project_number: int = Field(default=0)
    org: str = Field(default="", description="已废弃，请使用 owner")


class MasterAgentSettings(BaseModel):
    """Master agent settings for issue triage."""

    enabled: bool = True
    agent: str = "master-controller"
    backend: str | None = None
    model: str | None = None
    timeout_seconds: int = 300


class OrchestraSettings(BaseModel):
    """Orchestra daemon settings."""

    enabled: bool = True
    polling_interval: int = 60
    repo: str | None = None
    max_concurrent_flows: int = 3
    master_agent: MasterAgentSettings = Field(default_factory=MasterAgentSettings)


class VibeConfig(BaseModel):
    """Root configuration model."""

    flow: FlowConfig = Field(default_factory=FlowConfig)
    code_limits: CodeLimitsConfig = Field(default_factory=CodeLimitsConfig)
    review_scope: ReviewScopeConfig = Field(default_factory=ReviewScopeConfig)
    quality: QualityConfig = Field(default_factory=QualityConfig)
    pr_scoring: PRScoringConfig = Field(default_factory=PRScoringConfig)
    plan: PlanConfig = Field(default_factory=PlanConfig)
    run: RunConfig = Field(default_factory=RunConfig)
    review: ReviewConfig = Field(default_factory=ReviewConfig)
    github_project: GitHubProjectConfig = Field(default_factory=GitHubProjectConfig)
    ai: AIConfig = Field(default_factory=AIConfig)
    orchestra: OrchestraSettings = Field(default_factory=OrchestraSettings)

    @classmethod
    def from_yaml(cls, config_path: Path) -> "VibeConfig":
        """Load configuration from YAML file."""
        import yaml  # type: ignore[import-untyped]

        with open(config_path) as f:
            data = yaml.safe_load(f)
        return cls(**data)

    @classmethod
    def get_defaults(cls) -> "VibeConfig":
        """从 config/settings.yaml 读取配置（标准方式）。"""
        default_path = Path("config/settings.yaml")
        if default_path.exists():
            return cls.from_yaml(default_path)
        return cls()
