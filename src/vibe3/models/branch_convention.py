"""Backward compatibility re-export.

.. deprecated::
    Use `vibe3.config.branch_convention.BranchConvention` instead.
    This module re-exports BranchConvention for backward compatibility only.
    New code should import from the canonical location:

        from vibe3.config.branch_convention import BranchConvention
"""

from vibe3.config.branch_convention import BranchConvention

__all__ = ["BranchConvention"]
