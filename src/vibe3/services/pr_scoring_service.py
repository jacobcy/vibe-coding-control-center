"""PR Scoring service - 根据多维度指标计算 PR 风险分数."""

from enum import Enum

from loguru import logger
from pydantic import BaseModel

from vibe3.config.loader import get_config
from vibe3.exceptions import VibeError


class PRScoringError(VibeError):
    """PR 评分失败."""

    def __init__(self, details: str) -> None:
        super().__init__(f"PR scoring failed: {details}", recoverable=False)


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


def _format_trigger_factor(key: str, points: int) -> str:
    """Format a score contribution for terminal-friendly output."""
    return f"{key}(+{points})"


def _build_reason(score: RiskScore, dimensions: PRDimensions) -> str:
    """Build a short explanation for the current score."""
    reasons: list[str] = []

    if dimensions.critical_path_touch:
        reasons.append("touches critical path")
    if dimensions.public_api_touch:
        reasons.append("touches public API")
    if dimensions.changed_files >= 4:
        reasons.append("many files changed")
    if dimensions.changed_lines >= 200:
        reasons.append("large lines changed")
    if dimensions.impacted_modules >= 2:
        reasons.append("wide module impact")
    if dimensions.codex_verdict == "BLOCK":
        reasons.append("online review blocks")
    elif dimensions.codex_verdict == "CRITICAL":
        reasons.append("online review critical")
    elif dimensions.codex_verdict == "MAJOR":
        reasons.append("online review major")

    if not reasons:
        reasons.append("变更范围较小")

    suffix = "达到阻断阈值" if score.block else "未达到阻断阈值"
    return f"{'，'.join(reasons)}，{suffix}"


def _build_recommendations(score: RiskScore, dimensions: PRDimensions) -> list[str]:
    """Build actionable recommendations from the scoring dimensions."""
    recommendations: list[str] = []

    if dimensions.changed_files >= 4 or dimensions.changed_lines >= 200:
        recommendations.append("拆分 PR 以降低影响面")
    if dimensions.critical_path_touch:
        recommendations.append("补充关键路径回归测试")
    if dimensions.public_api_touch:
        recommendations.append("明确兼容性影响并补充调用侧验证")
    if dimensions.impacted_modules >= 2:
        recommendations.append("补充跨模块联动验证或说明影响范围")
    if dimensions.codex_verdict in {"MAJOR", "CRITICAL", "BLOCK"}:
        recommendations.append("先处理审查结论，再继续推进合并")

    if not recommendations and score.level in {RiskLevel.LOW, RiskLevel.MEDIUM}:
        recommendations.append("保持当前粒度，继续按常规测试和审查推进")

    return recommendations


def calculate_risk_score(dimensions: PRDimensions) -> RiskScore:
    """计算 PR 风险分数（从配置读取权重）.

    Args:
        dimensions: PR 评分维度

    Returns:
        风险评分结果

    Raises:
        PRScoringError: 评分失败
    """
    log = logger.bind(domain="pr_scoring", action="calculate_risk_score")
    log.info("Calculating PR risk score")

    try:
        config = get_config()
        w = config.pr_scoring.weights
        gate = config.pr_scoring.merge_gate
        t = config.pr_scoring.size_thresholds

        breakdown: dict[str, int] = {}

        # 改动行数
        cl = dimensions.changed_lines
        if cl > t.changed_lines.large:
            breakdown["changed_lines"] = w.changed_lines.xlarge
        elif cl > t.changed_lines.medium:
            breakdown["changed_lines"] = w.changed_lines.large
        elif cl >= t.changed_lines.small:
            breakdown["changed_lines"] = w.changed_lines.medium
        else:
            breakdown["changed_lines"] = w.changed_lines.small

        # 改动文件数
        cf = dimensions.changed_files
        if cf > t.changed_files.medium:  # >10
            breakdown["changed_files"] = w.changed_files.large
        elif cf >= t.changed_files.small:  # >=4
            breakdown["changed_files"] = w.changed_files.medium
        else:
            breakdown["changed_files"] = w.changed_files.small

        # 影响模块数
        im = dimensions.impacted_modules
        if im >= t.impacted_modules.medium:  # >=5
            breakdown["impacted_modules"] = w.impacted_modules.large
        elif im >= t.impacted_modules.small:  # >=2
            breakdown["impacted_modules"] = w.impacted_modules.medium
        else:
            breakdown["impacted_modules"] = w.impacted_modules.small

        # 布尔维度
        if dimensions.critical_path_touch:
            breakdown["critical_path_touch"] = w.critical_path_touch
        if dimensions.public_api_touch:
            breakdown["public_api_touch"] = w.public_api_touch
        if dimensions.cross_module_symbol_change:
            breakdown["cross_module_symbol_change"] = w.cross_module_symbol_change

        # Codex 审核结果
        if dimensions.codex_verdict == "CRITICAL":
            breakdown["codex_critical"] = w.codex_critical
        elif dimensions.codex_verdict == "MAJOR":
            breakdown["codex_major"] = w.codex_major

        score = sum(breakdown.values())
        level = determine_risk_level(score)
        block = score >= gate.block_on_score_at_or_above or (
            dimensions.codex_verdict in gate.block_on_verdict
        )

        result = RiskScore(score=score, level=level, breakdown=breakdown, block=block)
        log.bind(score=score, level=level, block=block).success("Risk score calculated")
        return result

    except PRScoringError:
        raise
    except Exception as e:
        raise PRScoringError(str(e)) from e


def determine_risk_level(score: int) -> RiskLevel:
    """根据分数判定风险等级（从配置读取阈值）.

    Args:
        score: 风险分数

    Returns:
        风险等级
    """
    t = get_config().pr_scoring.thresholds
    if score >= t.critical:
        return RiskLevel.CRITICAL
    elif score >= t.high:
        return RiskLevel.HIGH
    elif score >= t.medium:
        return RiskLevel.MEDIUM
    return RiskLevel.LOW


def generate_score_report(dimensions: PRDimensions) -> dict[str, object]:
    """生成完整评分报告.

    Args:
        dimensions: PR 评分维度

    Returns:
        评分报告 dict
    """
    log = logger.bind(domain="pr_scoring", action="generate_score_report")
    log.info("Generating score report")

    score = calculate_risk_score(dimensions)
    trigger_factors = [
        _format_trigger_factor(key, points)
        for key, points in score.breakdown.items()
        if points > 0
    ]
    report: dict[str, object] = {
        "score": score.score,
        "level": score.level,
        "block": score.block,
        "breakdown": score.breakdown,
        "dimensions": dimensions.model_dump(),
        "reason": _build_reason(score, dimensions),
        "trigger_factors": trigger_factors,
        "recommendations": _build_recommendations(score, dimensions),
    }
    log.bind(score=score.score, level=score.level).success("Score report generated")
    return report
