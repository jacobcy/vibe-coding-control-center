"""Re-export shim — PR status checker has moved to vibe3.services.pr.status_checker."""

from vibe3.services.pr.status_checker import (
    get_merged_pr_for_issue,
    has_merged_pr_for_issue,
)

__all__ = ["get_merged_pr_for_issue", "has_merged_pr_for_issue"]
