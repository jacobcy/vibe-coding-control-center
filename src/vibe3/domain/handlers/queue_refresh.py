"""Event handler for label/issue change -> queue priority refresh."""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

from vibe3.domain.handler_registry import register_handler
from vibe3.models.domain_events import LabelChanged

if TYPE_CHECKING:
    pass

_PRIORITY_LABEL_PREFIXES = ("priority/", "roadmap/")


@register_handler("LabelChanged")
def handle_label_changed(event: LabelChanged) -> None:
    """Trigger queue priority refresh when priority-affecting labels change."""
    if not any(event.label.startswith(p) for p in _PRIORITY_LABEL_PREFIXES):
        return

    logger.bind(
        domain="queue_refresh",
        issue_number=event.issue_number,
        label=event.label,
        action=event.action,
    ).info(
        f"Priority-affecting label {event.action}: {event.label} "
        f"on #{event.issue_number}, scheduling queue refresh"
    )

    try:
        from vibe3.domain.orchestration_facade import OrchestrationFacade

        facade = OrchestrationFacade._instance
        if facade and facade._coordinator:
            facade._coordinator.request_queue_refresh(event.issue_number)
    except Exception as exc:
        logger.bind(domain="queue_refresh").warning(
            f"Failed to schedule queue refresh: {exc}"
        )
