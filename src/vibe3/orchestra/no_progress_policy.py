"""Manager no-progress blocking policy (backward compatibility layer).

This module re-exports functions from runtime layer for backward compatibility.
"""

from vibe3.runtime.no_progress_policy import (
    _comment_count,
    _extract_issue_state_label,
    has_progress_changed,
    snapshot_progress,
)

__all__ = [
    "_comment_count",
    "_extract_issue_state_label",
    "has_progress_changed",
    "snapshot_progress",
]
