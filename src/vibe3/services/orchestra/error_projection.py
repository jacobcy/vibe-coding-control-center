"""Projection service that maps DomainEvents to error_log records.

This module implements ADR 0004's requirement for an explicit projection boundary
for events that should be recorded in the error_log instead of flow_events.
The projection is a publish hook on the global EventPublisher that writes to
error_log when a matching rule exists in the projection table.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

from vibe3.exceptions import E_ISSUE_FAILED, ErrorSeverity
from vibe3.models import IssueFailed
from vibe3.services.orchestra.error_tracking.service import ErrorTrackingService

if TYPE_CHECKING:
    from vibe3.models import DomainEvent, PublishHook


ERROR_PROJECTION_TABLE: dict[type[IssueFailed], tuple[str, ErrorSeverity]] = {
    IssueFailed: (str(E_ISSUE_FAILED), ErrorSeverity.ERROR),
}


def build_error_projection_hook() -> PublishHook:
    """Build a publish hook that projects domain events to error_log.

    Returns:
        A callable suitable for registering via EventPublisher.add_publish_hook().
    """

    def hook(event: DomainEvent) -> None:
        # Only process IssueFailed events
        if not isinstance(event, IssueFailed):
            return

        mapping = ERROR_PROJECTION_TABLE.get(type(event))
        if mapping is None:
            return

        error_code, severity = mapping
        try:
            ErrorTrackingService.get_instance().record_error(
                error_code=error_code,
                error_message=event.reason,
                issue_number=event.issue_number,
                severity=severity,
            )
        except Exception as e:
            logger.bind(domain="projection").error(
                f"Error projection failed for {type(event).__name__}: {e}"
            )

    return hook
