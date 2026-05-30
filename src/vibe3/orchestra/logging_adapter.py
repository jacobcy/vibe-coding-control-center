"""Logging adapter for domain layer to use orchestra logging.

This module provides OrchestraLoggingProtocol implementation,
enabling domain layer to log orchestra events without direct
orchestra.logging dependency (through protocol abstraction).
"""

from pathlib import Path

from vibe3.domain.protocols.logging_protocols import OrchestraLoggingProtocol
from vibe3.orchestra.logging import append_orchestra_event as _append_orchestra_event


class OrchestraLoggingAdapter(OrchestraLoggingProtocol):
    """Adapter for orchestra logging service.

    Implements OrchestraLoggingProtocol to enable dependency injection
    from domain layer.
    """

    def append_orchestra_event(
        self,
        event_type: str,
        data: dict,
        *,
        repo_root: Path | None = None,
    ) -> Path:
        """Append event to orchestra log.

        Args:
            event_type: Type of event (e.g., "heartbeat", "dispatch")
            data: Event data dictionary
            repo_root: Optional repository root path

        Returns:
            Path to orchestra events log file
        """
        # Convert dict to message string
        message = f"{event_type}: {data}"
        return _append_orchestra_event("domain", message, repo_root=repo_root)


# Convenience function for backward compatibility
def append_orchestra_event(
    component: str,
    message: str,
    *,
    level: str = "INFO",
    repo_root: Path | None = None,
) -> Path:
    """Append an event to the orchestra events log.

    This is a convenience function that delegates to orchestra.logging.
    Used by domain layer components that need simple event logging.

    Args:
        component: Component name (e.g., "dispatcher", "supervisor")
        message: Event message
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        repo_root: Optional repository root path

    Returns:
        Path to orchestra events log file
    """
    return _append_orchestra_event(component, message, level=level, repo_root=repo_root)
