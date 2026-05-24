"""PR Scoring models - PR 风险评分模型.

This module provides pure data models for PR scoring that are shared across
analysis and services layers. Moving these models to the analysis layer avoids
bidirectional dependencies between analysis and services.

Note: The scoring logic (generate_score_report, calculate_risk_score) remains
in services.pr_scoring_service as it depends on configuration and services.
"""

from enum import Enum

from pydantic import BaseModel


class RiskLevel(str, Enum):
    """风险等级."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class PRDimensions(BaseModel):
    """PR 评分维度输入."""

    changed_lines: int = 0
    changed_files: int = 0
    impacted_modules: int = 0
    critical_path_touch: bool = False
    public_api_touch: bool = False
    cross_module_symbol_change: bool = False
    codex_verdict: str | None = None  # "MAJOR" | "CRITICAL" | None


class RiskScore(BaseModel):
    """PR 风险评分结果."""

    score: int
    level: RiskLevel
    breakdown: dict[str, int]
    block: bool
