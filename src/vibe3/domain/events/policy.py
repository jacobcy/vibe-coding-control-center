"""Policy configuration domain events.

Re-exported from models layer to break the roles↔domain circular dependency.
See vibe3.models.domain_events for the canonical definitions.
"""

from vibe3.models import PolicyChanged

__all__ = ["PolicyChanged"]
