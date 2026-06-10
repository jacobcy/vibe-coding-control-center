"""Re-export shim for version service.

The actual implementation has moved to
vibe3.services.shared.versions.
"""

from vibe3.services.shared.versions import VersionService

__all__ = ["VersionService"]
