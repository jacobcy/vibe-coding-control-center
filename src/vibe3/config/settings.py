"""Configuration models using pydantic for type safety."""

from pathlib import Path

from pydantic import BaseModel, Field


class CodeLimitsConfig(BaseModel):
    """Code size limits configuration."""

    total_loc: int = Field(description="Total lines of code limit")
    max_file_loc: int = Field(description="Maximum lines per file")
    min_tests: int = Field(description="Minimum number of tests")


class V2ShellLimits(BaseModel):
    """V2 Shell code limits."""

    v2_shell: CodeLimitsConfig = Field(
        default_factory=lambda: CodeLimitsConfig(
            total_loc=7000, max_file_loc=300, min_tests=20
        )
    )


class V3PythonLimits(BaseModel):
    """V3 Python code limits."""

    v3_python: CodeLimitsConfig = Field(
        default_factory=lambda: CodeLimitsConfig(
            total_loc=7000, max_file_loc=300, min_tests=5
        )
    )


class CodeLimits(BaseModel):
    """Code limits for both V2 and V3."""

    v2_shell: CodeLimitsConfig = Field(
        default_factory=lambda: CodeLimitsConfig(
            total_loc=7000, max_file_loc=300, min_tests=20
        )
    )
    v3_python: CodeLimitsConfig = Field(
        default_factory=lambda: CodeLimitsConfig(
            total_loc=7000, max_file_loc=300, min_tests=5
        )
    )


class ReviewScopeConfig(BaseModel):
    """Review scope configuration."""

    critical_paths: list[str] = Field(
        default_factory=lambda: [
            "bin/",
            "lib/flow",
            "lib/git",
            "lib/github",
            "src/vibe3/services/",
        ],
        description="Critical paths for detailed review",
    )
    public_api_paths: list[str] = Field(
        default_factory=lambda: [
            "bin/vibe",
            "lib/flow.sh",
            "src/vibe3/commands/",
        ],
        description="Public API paths for compatibility checking",
    )


class TestCoverageConfig(BaseModel):
    """Test coverage requirements."""

    services: int = Field(
        default=80, ge=0, le=100, description="Services layer coverage %"
    )
    clients: int = Field(
        default=70, ge=0, le=100, description="Clients layer coverage %"
    )
    commands: int = Field(
        default=60, ge=0, le=100, description="Commands layer coverage %"
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


class VibeConfig(BaseModel):
    """Root configuration model for Vibe Center."""

    code_limits: CodeLimits = Field(default_factory=CodeLimits)
    review_scope: ReviewScopeConfig = Field(default_factory=ReviewScopeConfig)
    quality: QualityConfig = Field(default_factory=QualityConfig)
    pr_scoring: PRScoringConfig = Field(default_factory=PRScoringConfig)

    @classmethod
    def from_yaml(cls, config_path: Path) -> "VibeConfig":
        """Load configuration from YAML file.

        Args:
            config_path: Path to configuration file

        Returns:
            VibeConfig instance
        """
        import yaml

        with open(config_path) as f:
            data = yaml.safe_load(f)

        return cls(**data)
