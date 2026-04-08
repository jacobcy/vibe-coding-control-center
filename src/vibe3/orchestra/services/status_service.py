"""Status service compatibility stub.

This module re-exports OrchestraStatusService from services layer
for backward compatibility. All implementations have been moved to
services.orchestra_status_service.
"""

from vibe3.services.orchestra_status_service import (
    IssueStatusEntry,
    OrchestraSnapshot,
    OrchestraStatusService,
    format_issue_runtime_line,
    format_issue_summary_line,
    is_running_issue,
)

__all__ = [
    "IssueStatusEntry",
    "OrchestraSnapshot",
    "OrchestraStatusService",
    "format_issue_runtime_line",
    "format_issue_summary_line",
    "is_running_issue",
]
