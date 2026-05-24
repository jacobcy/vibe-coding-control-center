"""Re-export BranchConvention from config layer for backward compatibility.

This module re-exports BranchConvention from config.branch_convention
to maintain backward compatibility for existing imports.
"""

from vibe3.config.branch_convention import BranchConvention

__all__ = ["BranchConvention"]
