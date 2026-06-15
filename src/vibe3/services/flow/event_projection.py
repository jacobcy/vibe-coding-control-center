"""Projection service that maps DomainEvents to flow_events timeline records.

This module implements ADR 0004's requirement for an explicit projection boundary
between domain events and flow timeline events. The projection is a publish hook
on the global EventPublisher that writes to flow_events when a matching rule
exists in the projection table.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

from vibe3.clients import SQLiteClient
from vibe3.models import DomainEvent, FlowBlocked, FlowCompleted, PRMerged

if TYPE_CHECKING:
    from vibe3.models import PublishHook


# Declarative mapping from DomainEvent types to flow_events.event_type strings.
# Events not in this table are not projected.
PROJECTION_TABLE: dict[type[DomainEvent], str] = {
    FlowBlocked: "flow_blocked",
    FlowCompleted: "flow_completed",
    PRMerged: "pr_merged",
}


def project_domain_event(event: DomainEvent) -> bool:
    """Project a domain event to flow_events if it's in the projection table.

    Args:
        event: The domain event to potentially project.

    Returns:
        True if the event was projected, False if it's not in the projection table.
    """
    event_class = type(event)
    event_type = PROJECTION_TABLE.get(event_class)

    if event_type is None:
        return False

    # All events in the projection table must have a branch field.
    # This is enforced by the projection table design (only events with branch
    # are added). If an event lacks branch, it's a configuration error.
    branch = getattr(event, "branch", None)
    if branch is None:
        logger.bind(domain="projection").warning(
            f"Event {event_class.__name__} in projection table lacks "
            "branch field, skipping"
        )
        return False

    # Extract actor from the event (default to "system")
    actor = getattr(event, "actor", "system")

    # Build detail from key event fields
    # For FlowCompleted, include completed_state
    # For FlowBlocked, include blocked_reason
    # For PRMerged, include pr_number and merged_by
    detail_parts = []
    if hasattr(event, "completed_state"):
        detail_parts.append(f"completed_state={event.completed_state}")
    if hasattr(event, "blocked_reason"):
        detail_parts.append(f"blocked_reason={event.blocked_reason}")
    if hasattr(event, "issue_number"):
        detail_parts.append(f"issue_number={event.issue_number}")
    if hasattr(event, "pr_number"):
        detail_parts.append(f"pr_number={event.pr_number}")
    if hasattr(event, "merged_by") and event.merged_by is not None:
        detail_parts.append(f"merged_by={event.merged_by}")
    detail = ", ".join(detail_parts) if detail_parts else None

    # Build refs dict with issue_number and pr_number if available
    refs = None
    if hasattr(event, "issue_number"):
        refs = {"issue_number": event.issue_number}
    if hasattr(event, "pr_number"):
        refs = refs or {}
        refs["pr_number"] = event.pr_number

    # Write to flow_events
    store = SQLiteClient()
    store.add_event(
        branch=branch,
        event_type=event_type,
        actor=actor,
        detail=detail,
        refs=refs,
    )

    logger.bind(domain="projection", event_type=event_type, branch=branch).info(
        f"Projected {event_class.__name__} to flow_events"
    )

    return True


def build_event_projection_hook() -> PublishHook:
    """Build a publish hook that projects domain events to flow_events.

    The hook catches and logs all exceptions without re-raising, ensuring
    that projection failures never break the domain event handler chain.

    Returns:
        A callable suitable for registering via EventPublisher.add_publish_hook().
    """

    def hook(event: DomainEvent) -> None:
        try:
            project_domain_event(event)
        except Exception as e:
            logger.bind(domain="projection").error(
                f"Projection failed for {type(event).__name__}: {e}"
            )

    return hook
