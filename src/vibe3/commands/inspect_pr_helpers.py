"""PR helpers for inspect command.

Note: PR analysis logic has been moved to services.pr_analysis_service
to remove the service->command reverse dependency. This module re-exports
build_pr_analysis for backward compatibility.
"""

# Re-export types for backward compatibility
from vibe3.models.pr_analysis import (  # noqa: F401
    CommitInfo,
    CriticalFileInfo,
    PRCriticalAnalysis,
)
from vibe3.services.pr_analysis_service import build_pr_analysis  # noqa: F401

__all__ = ["build_pr_analysis", "CommitInfo", "CriticalFileInfo", "PRCriticalAnalysis"]
