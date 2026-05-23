"""Queue entry data structure."""

from dataclasses import dataclass


@dataclass
class QueueEntry:
    """Frozen queue entry tracked only by issue identity and wait state."""

    issue_number: int
    collected_state: str | None = None
    waiting_state: str | None = None
    retry_count: int = 0
    last_attempted_at: str | None = None
