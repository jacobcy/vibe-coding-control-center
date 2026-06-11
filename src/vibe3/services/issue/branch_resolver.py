"""Helpers for resolving issue numbers to canonical flow branches.

DEPRECATED: This module now re-exports from shared.branch_resolver
for backward compatibility.
New code should import directly from vibe3.services.shared.branch_resolver.
"""

from vibe3.services.shared.branch_resolver import (
    _format_flow_details,
    _resolve_best_flow_from_candidates,
    iter_issue_branch_candidates,
    resolve_issue_branch_input,
)

__all__ = [
    "iter_issue_branch_candidates",
    "resolve_issue_branch_input",
    "_format_flow_details",
    "_resolve_best_flow_from_candidates",
]
