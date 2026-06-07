"""Inspect command helper functions.

Re-exports from analysis/service layers for backward compatibility.
The actual implementation lives in:
- vibe3.analysis.inspect_query_service  (build_change_analysis)
- vibe3.services.pr_analysis_service   (PR analysis helpers)
- vibe3.commands.inspect_pr_helpers     (build_pr_analysis re-export)
"""

import typer

from vibe3.analysis.inspect_query_service import (  # noqa: F401
    build_change_analysis,
)
from vibe3.commands.inspect_pr_helpers import build_pr_analysis  # noqa: F401
from vibe3.models.pr_analysis import (  # noqa: F401
    CommitInfo,
    CriticalFileInfo,
    PRCriticalAnalysis,
)
from vibe3.services.pr.analysis import (  # noqa: F401 - backward compat re-exports
    analyze_critical_files,
    calculate_pr_risk_score,
    filter_critical_files,
    get_pr_changed_files,
    get_pr_commit_count,
    get_recent_commits,
)


def suggest_next_step(context: str, quiet: bool = False) -> None:
    """Print suggested next commands based on context.

    Args:
        context: Context identifier for suggestion lookup
        quiet: If True, suppress suggestions (for script use)
    """
    if quiet:
        return

    suggestions: dict[str, str] = {
        "inspect_base": ("\n→ vibe3 snapshot diff [base]  (see project-level changes)"),
        "inspect_files": (
            "\n→ vibe3 inspect symbols <file>:<func>  (see symbol usage)"
        ),
        "inspect_symbols": ("\n→ vibe3 inspect dead-code  (check for unused code)"),
        "inspect_dead_code": (
            "\n→ vibe3 inspect symbols <file>:<func>  (verify findings)"
        ),
        "snapshot_diff": ("\n→ vibe3 inspect base [base]  (see code-level impact)"),
        "snapshot_show": ("\n→ vibe3 inspect files <path>  (see file details)"),
    }

    if context in suggestions:
        typer.echo(suggestions[context])


__all__ = [
    "CriticalFileInfo",
    "CommitInfo",
    "PRCriticalAnalysis",
    "build_change_analysis",
    "build_pr_analysis",
    "get_pr_changed_files",
    "filter_critical_files",
    "analyze_critical_files",
    "calculate_pr_risk_score",
    "get_recent_commits",
    "get_pr_commit_count",
    "suggest_next_step",
]
