"""Re-export shim for LOC service.

The actual implementation has moved to
vibe3.services.shared.loc.
"""

from vibe3.services.shared.loc import LocService, LOCStats

__all__ = ["LOCStats", "LocService"]
