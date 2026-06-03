"""Base class for all domain events."""

from dataclasses import dataclass


@dataclass(frozen=True)
class DomainEvent:
    """Base class for all domain events.

    All domain events should inherit from this class.
    Events are immutable (frozen) to ensure event integrity.
    """

    pass
