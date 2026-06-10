"""Re-export shim for issue branch resolver.

The actual implementation has moved to
vibe3.services.issue.branch_resolver.
"""

from vibe3.services.issue.branch_resolver import (
    _format_flow_details,
    iter_issue_branch_candidates,
    resolve_issue_branch_input,
)

__all__ = [
    "_format_flow_details",
    "iter_issue_branch_candidates",
    "resolve_issue_branch_input",
]
