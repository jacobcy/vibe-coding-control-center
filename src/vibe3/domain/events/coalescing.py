"""Dispatch intent coalescing for issue-level debounce.

Coalesces multiple dispatch intents for the same issue within a single heartbeat tick,
ensuring only the latest intent per (issue_number, event_type) is processed.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from loguru import logger

from vibe3.domain.events.base import DomainEvent

if TYPE_CHECKING:
    pass


@dataclass
class CoalesceRecord:
    """Record of a coalesced (merged) event."""

    issue_number: int
    event_type: str
    merged_count: int  # How many events were merged into the final one
    kept_payload_summary: dict[str, str]  # Key fields from the winning event


@dataclass
class DispatchCoalescer:
    """Coalesces dispatch intents within a single heartbeat tick.

    Maintains a per-tick buffer of pending *DispatchIntent events, keyed by
    (issue_number, event_type_name). When multiple intents with the same key
    are published within one tick, only the latest is retained (latest-wins).

    Thread-safety: Single-threaded within heartbeat tick
    (same as GlobalDispatchCoordinator), no locking needed.

    Only coalesces events with issue_number attribute (dispatch intents).
    Other events pass through unbuffered.
    """

    _tick_id: int = 0
    _buffer: dict[tuple[str, int], DomainEvent] = field(default_factory=dict)
    _merge_counts: dict[tuple[str, int], int] = field(default_factory=dict)
    _payload_summaries: dict[tuple[str, int], dict[str, str]] = field(
        default_factory=dict
    )

    def start_tick(self, tick_id: int) -> None:
        """Start a new tick, resetting the buffer.

        Args:
            tick_id: Current tick number from heartbeat
        """
        if self._buffer:
            # Buffer not empty - previous tick didn't call end_tick()
            logger.bind(domain="coalescer").warning(
                f"start_tick({tick_id}) called with non-empty buffer, "
                f"resetting (previous tick_id={self._tick_id})"
            )

        self._tick_id = tick_id
        self._buffer.clear()
        self._merge_counts.clear()
        self._payload_summaries.clear()

    def coalesce(self, event: DomainEvent) -> DomainEvent | None:
        """Coalesce a dispatch intent event.

        Args:
            event: Event to coalesce

        Returns:
            - None if event was absorbed into an existing buffer entry
            - The event itself if it's a pass-through (non-dispatch-intent)
        """
        # Check if event has issue_number attribute (dispatch intent)
        if not hasattr(event, "issue_number"):
            # Pass-through: non-dispatch-intent events are not buffered
            return event

        event_type = type(event).__name__
        issue_number = getattr(event, "issue_number")
        key = (event_type, issue_number)

        if key in self._buffer:
            # Merge: replace with newer event (latest wins)
            self._merge_counts[key] = self._merge_counts.get(key, 0) + 1

            # Extract key fields for logging
            payload_summary = self._extract_payload_summary(event)

            logger.bind(
                domain="coalescer",
                tick_id=self._tick_id,
                issue_number=issue_number,
                event_type=event_type,
                merged_count=self._merge_counts[key],
            ).info(
                f"Coalesced {event_type} for #{issue_number} "
                f"(merged {self._merge_counts[key]} events)"
            )

            self._buffer[key] = event
            self._payload_summaries[key] = payload_summary
            return None  # Absorbed

        # First occurrence: buffer it
        self._buffer[key] = event
        self._merge_counts[key] = 0
        self._payload_summaries[key] = self._extract_payload_summary(event)

        logger.bind(
            domain="coalescer",
            tick_id=self._tick_id,
            issue_number=issue_number,
            event_type=event_type,
        ).debug(f"Buffered {event_type} for #{issue_number}")

        # Return None to indicate event was absorbed (buffered for later flush)
        return None

    def flush(self) -> list[DomainEvent]:
        """Flush buffered events and clear the buffer.

        Returns:
            List of buffered events (deduplicated)
        """
        events = list(self._buffer.values())

        logger.bind(
            domain="coalescer",
            tick_id=self._tick_id,
            event_count=len(events),
        ).debug(f"Flushed {len(events)} buffered events")

        self._buffer.clear()
        return events

    def end_tick(self) -> list[CoalesceRecord]:
        """End the current tick and return coalescing stats.

        Returns:
            List of CoalesceRecord for events that were merged
        """
        records: list[CoalesceRecord] = []

        for key, merged_count in self._merge_counts.items():
            if merged_count > 0:
                event_type, issue_number = key
                payload_summary = self._payload_summaries.get(key, {})

                records.append(
                    CoalesceRecord(
                        issue_number=issue_number,
                        event_type=event_type,
                        merged_count=merged_count,
                        kept_payload_summary=payload_summary,
                    )
                )

        logger.bind(
            domain="coalescer",
            tick_id=self._tick_id,
            coalesced_count=len(records),
        ).info(f"Tick {self._tick_id} complete: {len(records)} coalesced events")

        # Clear state
        self._buffer.clear()
        self._merge_counts.clear()
        self._payload_summaries.clear()

        return records

    def _extract_payload_summary(self, event: DomainEvent) -> dict[str, str]:
        """Extract key fields from an event for logging.

        Args:
            event: Event to summarize

        Returns:
            Dict of field name -> string value for key fields
        """
        summary: dict[str, str] = {}

        # Common fields for dispatch intents
        for field_name in ["issue_number", "branch", "trigger_state", "actor"]:
            if hasattr(event, field_name):
                value = getattr(event, field_name)
                summary[field_name] = str(value)

        return summary
