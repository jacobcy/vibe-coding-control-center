"""Base class for all domain events.

Re-exported from models layer to break L3 circular dependencies.
See vibe3.models.domain_events for the canonical definition.
"""

from vibe3.models.domain_events import DomainEvent

__all__ = ["DomainEvent"]
