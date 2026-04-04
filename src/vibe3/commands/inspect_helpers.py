"""Inspect command helper functions.

Re-exports from analysis/service layers for backward compatibility.
The actual implementation lives in:
- vibe3.analysis.inspect_query_service  (build_change_analysis, validate_pr_number)
- vibe3.services.pr_analysis_service   (PR analysis helpers)
- vibe3.commands.inspect_pr_helpers     (build_pr_analysis re-export)
"""

from vibe3.analysis.inspect_query_service import (  # noqa: F401
    build_change_analysis,
    validate_pr_number,
)
from vibe3.commands.inspect_pr_helpers import build_pr_analysis  # noqa: F401
from vibe3.models.pr_analysis import (  # noqa: F401
    CommitInfo,
    CriticalFileInfo,
    PRCriticalAnalysis,
)
from vibe3.services.pr_analysis_service import (  # noqa: F401 - backward compat re-exports
    _analyze_critical_files,
    _calculate_risk_score,
    _filter_critical_files,
    _get_pr_changed_files,
    _get_pr_commit_count,
    _get_recent_commits,
)

__all__ = [
    "CriticalFileInfo",
    "CommitInfo",
    "PRCriticalAnalysis",
    "build_change_analysis",
    "validate_pr_number",
    "build_pr_analysis",
    "_get_pr_changed_files",
    "_filter_critical_files",
    "_analyze_critical_files",
    "_calculate_risk_score",
    "_get_recent_commits",
    "_get_pr_commit_count",
]
