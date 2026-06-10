"""Re-export shim for label service.

The actual implementation has moved to
vibe3.services.shared.label_service.
"""

from vibe3.services.shared.label_service import LabelService

__all__ = ["LabelService"]
