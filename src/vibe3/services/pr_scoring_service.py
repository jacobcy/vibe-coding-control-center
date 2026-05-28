"""PR Scoring service - 根据多维度指标计算 PR 风险分数.

This module re-exports PR scoring logic from vibe3.analysis.pr_scoring for backward
compatibility. The actual implementation lives in the analysis layer to avoid
bidirectional dependencies between analysis and services.
"""

from vibe3.analysis.pr_scoring import (
    PRDimensions,
    RiskLevel,
    RiskScore,
    calculate_risk_score,
    determine_risk_level,
    generate_score_report,
)
from vibe3.exceptions import VibeError


class PRScoringError(VibeError):
    """PR 评分失败."""

    def __init__(self, details: str) -> None:
        super().__init__(f"PR scoring failed: {details}", recoverable=False)


__all__ = [
    "PRDimensions",
    "PRScoringError",
    "RiskLevel",
    "RiskScore",
    "calculate_risk_score",
    "determine_risk_level",
    "generate_score_report",
]
