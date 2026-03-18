"""Configuration models using pydantic for type safety.

配置真源原则：
- config/settings.yaml 是配置的真源
- Pydantic 模型只提供最小安全默认值（用于降级场景）
- 正常情况下所有配置都从 YAML 文件读取
"""

from pathlib import Path

from pydantic import BaseModel, Field


class TestFileLimitsConfig(BaseModel):
    """Per-layer test file line limits."""

    services: int = Field(
        default=500, description="Services layer max lines per test file"
    )  # 宽松默认值
    clients: int = Field(
        default=500, description="Clients layer max lines per test file"
    )
    commands: int = Field(
        default=300, description="Commands layer max lines per test file"
    )


class CodeLimitsConfig(BaseModel):
    """Code size limits configuration."""

    total_loc: int = Field(default=10000, description="Total lines of code limit")
    max_file_loc: int = Field(default=500, description="Maximum lines per file")
    min_tests: int = Field(default=0, description="Minimum number of tests")
    test_file_loc: TestFileLimitsConfig = Field(
        default_factory=TestFileLimitsConfig,
        description="Per-layer test file line limits",
    )


class CodeLimits(BaseModel):
    """Code limits for both V2 and V3."""

    v2_shell: CodeLimitsConfig = Field(
        default_factory=CodeLimitsConfig, description="V2 Shell code limits"
    )
    v3_python: CodeLimitsConfig = Field(
        default_factory=CodeLimitsConfig, description="V3 Python code limits"
    )


class ReviewScopeConfig(BaseModel):
    """Review scope configuration."""

    critical_paths: list[str] = Field(
        default_factory=list,
        description="Critical paths for detailed review",
    )
    public_api_paths: list[str] = Field(
        default_factory=list,
        description="Public API paths for compatibility checking",
    )


class TestCoverageConfig(BaseModel):
    """Test coverage requirements."""

    services: int = Field(
        default=50, ge=0, le=100, description="Services layer coverage %"
    )
    clients: int = Field(
        default=50, ge=0, le=100, description="Clients layer coverage %"
    )
    commands: int = Field(
        default=50, ge=0, le=100, description="Commands layer coverage %"
    )


class QualityConfig(BaseModel):
    """Quality standards configuration."""

    test_coverage: TestCoverageConfig = Field(
        default_factory=TestCoverageConfig, description="Test coverage requirements"
    )


class LineChangeWeights(BaseModel):
    """Weights for changed lines."""

    small: int = Field(default=0, description="<50 lines")
    medium: int = Field(default=1, description="50-200 lines")
    large: int = Field(default=2, description="200-500 lines")
    xlarge: int = Field(default=3, description=">500 lines")


class FileChangeWeights(BaseModel):
    """Weights for changed files."""

    small: int = Field(default=0, description="1-3 files")
    medium: int = Field(default=1, description="4-10 files")
    large: int = Field(default=2, description=">10 files")


class ModuleChangeWeights(BaseModel):
    """Weights for impacted modules."""

    small: int = Field(default=0, description="1 module")
    medium: int = Field(default=1, description="2-4 modules")
    large: int = Field(default=2, description="≥5 modules")


class PRScoringWeights(BaseModel):
    """PR scoring weights configuration."""

    changed_lines: LineChangeWeights = Field(default_factory=LineChangeWeights)
    changed_files: FileChangeWeights = Field(default_factory=FileChangeWeights)
    impacted_modules: ModuleChangeWeights = Field(default_factory=ModuleChangeWeights)
    critical_path_touch: int = Field(
        default=2, description="Weight for touching critical paths"
    )
    public_api_touch: int = Field(
        default=2, description="Weight for touching public APIs"
    )
    cross_module_symbol_change: int = Field(
        default=2, description="Weight for cross-module symbol changes"
    )
    codex_major: int = Field(default=3, description="Weight for Codex MAJOR verdict")
    codex_critical: int = Field(
        default=5, description="Weight for Codex CRITICAL verdict"
    )


class PRScoringThresholds(BaseModel):
    """PR scoring risk thresholds."""

    medium: int = Field(default=3, description="Medium risk threshold")
    high: int = Field(default=6, description="High risk threshold")
    critical: int = Field(default=9, description="Critical risk threshold")


class MergeGateConfig(BaseModel):
    """Merge gate configuration."""

    block_on_score_at_or_above: int = Field(
        default=9, description="Block PR if score >= this value"
    )
    block_on_verdict: list[str] = Field(
        default_factory=lambda: ["BLOCK"], description="Block on these Codex verdicts"
    )


class PRScoringConfig(BaseModel):
    """PR scoring configuration."""

    weights: PRScoringWeights = Field(default_factory=PRScoringWeights)
    thresholds: PRScoringThresholds = Field(default_factory=PRScoringThresholds)
    merge_gate: MergeGateConfig = Field(default_factory=MergeGateConfig)


class HooksConfig(BaseModel):
    """Git hooks configuration."""

    post_commit: bool = True
    pre_push: bool = False


class AutoTriggerConfig(BaseModel):
    """Auto trigger configuration for review."""

    enabled: bool = True
    min_complexity: int = Field(default=3, ge=1, le=10)
    min_lines_changed: int = 50
    min_files_changed: int = 3
    hooks: HooksConfig = Field(default_factory=HooksConfig)


class ReviewConfig(BaseModel):
    """Review configuration."""

    auto_trigger: AutoTriggerConfig = Field(default_factory=AutoTriggerConfig)


class VibeConfig(BaseModel):
    """Root configuration model for Vibe Center.

    配置真源：config/settings.yaml

    Pydantic 模型中的默认值是最小安全默认值，仅用于降级场景。
    正常情况下所有配置都应该从 YAML 文件读取。
    """

    code_limits: CodeLimits = Field(default_factory=CodeLimits)
    review_scope: ReviewScopeConfig = Field(default_factory=ReviewScopeConfig)
    quality: QualityConfig = Field(default_factory=QualityConfig)
    pr_scoring: PRScoringConfig = Field(default_factory=PRScoringConfig)
    review: ReviewConfig = Field(default_factory=ReviewConfig)

    @classmethod
    def from_yaml(cls, config_path: Path) -> "VibeConfig":
        """Load configuration from YAML file.

        Args:
            config_path: Path to configuration file

        Returns:
            VibeConfig instance
        """
        import yaml  # type: ignore[import-untyped]

        with open(config_path) as f:
            data = yaml.safe_load(f)

        return cls(**data)

    @classmethod
    def get_defaults(cls) -> "VibeConfig":
        """从默认配置文件 config/settings.yaml 读取配置.

        这是获取配置的标准方式，确保 YAML 文件是唯一真源。

        Returns:
            从 config/settings.yaml 加载的配置，如果文件不存在则返回最小安全默认值
        """
        default_path = Path("config/settings.yaml")
        if default_path.exists():
            return cls.from_yaml(default_path)
        return cls()
