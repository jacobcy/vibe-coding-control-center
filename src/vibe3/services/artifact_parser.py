"""Re-export shim for artifact parser.

The actual implementation has moved to
vibe3.services.shared.artifacts.
"""

from vibe3.services.shared.artifacts import ArtifactParser

__all__ = ["ArtifactParser"]
