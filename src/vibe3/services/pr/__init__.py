"""PR domain services subpackage."""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from vibe3.analysis import (
        PRDimensions,
        RiskLevel,
        RiskScore,
        calculate_risk_score,
        determine_risk_level,
        generate_score_report,
    )
    from vibe3.services.pr.analysis import (
        analyze_critical_files,
        build_pr_analysis,
        calculate_pr_risk_score,
        filter_critical_files,
        get_pr_changed_files,
        get_pr_commit_count,
        get_recent_commits,
    )
    from vibe3.services.pr.create import PRCreateResult, PRCreateUsecase
    from vibe3.services.pr.loc_comment import PRLocCommentService
    from vibe3.services.pr.ready import PrReadyAbortedError, PrReadyUsecase
    from vibe3.services.pr.resolver import (
        resolve_branch_from_pr,
        resolve_command_branch,
    )
    from vibe3.services.pr.review import PRReviewBriefingService
    from vibe3.services.pr.scoring import PRScoringError
    from vibe3.services.pr.service import PRService
    from vibe3.services.pr.status_checker import (
        get_merged_pr_for_issue,
        has_merged_pr_for_issue,
    )
    from vibe3.services.pr.utils import (
        build_pr_body,
        check_upstream_conflicts,
        get_metadata_from_flow,
    )
    from vibe3.services.pr.verdict_policy import (
        blocks_merge,
        passes_review,
        requires_audit_ref,
    )
    from vibe3.services.pr.verdict_service import VerdictService

__all__ = [
    # Classes
    "PRCreateResult",
    "PRCreateUsecase",
    "PRDimensions",
    "PRLocCommentService",
    "PRReviewBriefingService",
    "PRScoringError",
    "PRService",
    "PrReadyAbortedError",
    "PrReadyUsecase",
    "RiskLevel",
    "RiskScore",
    "VerdictService",
    # Functions
    "analyze_critical_files",
    "blocks_merge",
    "build_pr_analysis",
    "build_pr_body",
    "calculate_pr_risk_score",
    "calculate_risk_score",
    "check_upstream_conflicts",
    "determine_risk_level",
    "filter_critical_files",
    "generate_score_report",
    "get_merged_pr_for_issue",
    "get_metadata_from_flow",
    "get_pr_changed_files",
    "get_pr_commit_count",
    "get_recent_commits",
    "has_merged_pr_for_issue",
    "passes_review",
    "requires_audit_ref",
    "resolve_branch_from_pr",
    "resolve_command_branch",
]

_SYMBOL_MODULES = {
    # Classes
    "PRCreateResult": "vibe3.services.pr.create",
    "PRCreateUsecase": "vibe3.services.pr.create",
    "PRDimensions": "vibe3.analysis",
    "PRLocCommentService": "vibe3.services.pr.loc_comment",
    "PRReviewBriefingService": "vibe3.services.pr.review",
    "PRScoringError": "vibe3.services.pr.scoring",
    "PRService": "vibe3.services.pr.service",
    "PrReadyAbortedError": "vibe3.services.pr.ready",
    "PrReadyUsecase": "vibe3.services.pr.ready",
    "RiskLevel": "vibe3.analysis",
    "RiskScore": "vibe3.analysis",
    "VerdictService": "vibe3.services.pr.verdict_service",
    # Functions
    "analyze_critical_files": "vibe3.services.pr.analysis",
    "blocks_merge": "vibe3.services.pr.verdict_policy",
    "build_pr_analysis": "vibe3.services.pr.analysis",
    "build_pr_body": "vibe3.services.pr.utils",
    "calculate_pr_risk_score": "vibe3.services.pr.analysis",
    "calculate_risk_score": "vibe3.analysis",
    "check_upstream_conflicts": "vibe3.services.pr.utils",
    "determine_risk_level": "vibe3.analysis",
    "filter_critical_files": "vibe3.services.pr.analysis",
    "generate_score_report": "vibe3.analysis",
    "get_merged_pr_for_issue": "vibe3.services.pr.status_checker",
    "get_metadata_from_flow": "vibe3.services.pr.utils",
    "get_pr_changed_files": "vibe3.services.pr.analysis",
    "get_pr_commit_count": "vibe3.services.pr.analysis",
    "get_recent_commits": "vibe3.services.pr.analysis",
    "has_merged_pr_for_issue": "vibe3.services.pr.status_checker",
    "passes_review": "vibe3.services.pr.verdict_policy",
    "requires_audit_ref": "vibe3.services.pr.verdict_policy",
    "resolve_branch_from_pr": "vibe3.services.pr.resolver",
    "resolve_command_branch": "vibe3.services.pr.resolver",
}


def __getattr__(name: str) -> Any:
    """Lazy import for PR services symbols to avoid circular dependencies.

    This allows external modules to use:
        from vibe3.services.pr import PRService, PRCreateUsecase

    While avoiding circular imports at module load time.
    """
    if name in _SYMBOL_MODULES:
        import importlib

        module = importlib.import_module(_SYMBOL_MODULES[name])
        symbol = getattr(module, name)
        # Cache in module globals for faster subsequent access
        globals()[name] = symbol
        return symbol

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
