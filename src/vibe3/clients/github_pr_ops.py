"""GitHub client PR operations (re-export module).

This module provides backward compatibility by re-exporting
PRReadMixin and PRWriteMixin. New code should import from
github_pr_read_ops and github_pr_write_ops directly.
"""

from vibe3.clients.github_pr_read_ops import PRReadMixin
from vibe3.clients.github_pr_write_ops import PRWriteMixin


class PRMixin(PRReadMixin, PRWriteMixin):
    """Composite mixin for all PR operations.

    Combines read and write operations for backward compatibility.
    """

    pass


__all__ = ["PRMixin", "PRReadMixin", "PRWriteMixin"]
