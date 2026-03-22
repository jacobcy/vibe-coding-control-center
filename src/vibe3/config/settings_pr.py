"""PR scoring configuration models."""

from pydantic import BaseModel, Field


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
    critical_path_touch: int = Field(default=2)
    public_api_touch: int = Field(default=2)
    cross_module_symbol_change: int = Field(default=2)
    codex_major: int = Field(default=3)
    codex_critical: int = Field(default=5)


class PRScoringThresholds(BaseModel):
    """PR scoring risk thresholds."""

    medium: int = Field(default=3)
    high: int = Field(default=6)
    critical: int = Field(default=9)


class MergeGateConfig(BaseModel):
    """Merge gate configuration."""

    block_on_score_at_or_above: int = Field(default=9)
    block_on_verdict: list[str] = Field(default_factory=lambda: ["BLOCK"])


class SizeThreshold(BaseModel):
    """Threshold values for size classification."""

    small: int = Field(default=50)
    medium: int = Field(default=200)
    large: int = Field(default=500)


class SizeThresholds(BaseModel):
    """Size thresholds for each dimension."""

    changed_lines: SizeThreshold = Field(default_factory=SizeThreshold)
    changed_files: SizeThreshold = Field(
        default_factory=lambda: SizeThreshold(small=4, medium=10, large=20)
    )
    impacted_modules: SizeThreshold = Field(
        default_factory=lambda: SizeThreshold(small=2, medium=5, large=10)
    )


class PRScoringConfig(BaseModel):
    """PR scoring configuration."""

    size_thresholds: SizeThresholds = Field(default_factory=SizeThresholds)
    weights: PRScoringWeights = Field(default_factory=PRScoringWeights)
    thresholds: PRScoringThresholds = Field(default_factory=PRScoringThresholds)
    merge_gate: MergeGateConfig = Field(default_factory=MergeGateConfig)
