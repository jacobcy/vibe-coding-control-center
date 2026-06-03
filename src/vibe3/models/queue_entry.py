"""Queue entry data contract."""

from dataclasses import dataclass


@dataclass
class QueueEntry:
    """Frozen queue entry tracked only by issue identity and wait state.

    Attributes:
        issue_number: GitHub issue number identifier
        collected_state: State at collection time (e.g., "ready", "blocked")
        waiting_state: State awaiting dispatch confirmation (None if not dispatched)
    """

    issue_number: int
    collected_state: str | None = None
    waiting_state: str | None = None
