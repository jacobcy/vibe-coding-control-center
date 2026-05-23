"""Data models for blocked state management."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class BlockedState:
    """Represents blocked state from a single source."""

    is_blocked: bool
    blocked_reason: str | None = None
    blocked_by: list[int] | None = None
    state: str | None = None  # "active", "blocked", "done", etc.

    @classmethod
    def not_blocked(cls) -> BlockedState:
        """Create a non-blocked state."""
        return cls(is_blocked=False)

    @classmethod
    def blocked(
        cls,
        reason: str,
        blocked_by: list[int] | None = None,
    ) -> BlockedState:
        """Create a blocked state."""
        return cls(
            is_blocked=True,
            blocked_reason=reason,
            blocked_by=blocked_by or [],
            state="blocked",
        )


@dataclass
class ConsistencyReport:
    """Report on three-source consistency."""

    database_state: BlockedState
    body_state: BlockedState
    label_state: BlockedState

    @property
    def is_consistent(self) -> bool:
        """True if all three sources agree on blocked status."""
        return (
            self.database_state.is_blocked == self.body_state.is_blocked
            and self.body_state.is_blocked == self.label_state.is_blocked
        )

    @property
    def authoritative_state(self) -> BlockedState:
        """Returns the truth-source state (issue body)."""
        return self.body_state
