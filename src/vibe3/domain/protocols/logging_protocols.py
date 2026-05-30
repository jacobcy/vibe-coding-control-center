"""Logging-related protocols for domain layer.

Enables domain layer to log orchestra events without depending on
orchestra implementation.
"""

from pathlib import Path
from typing import Protocol


class OrchestraLoggingProtocol(Protocol):
    """Protocol for orchestra logging operations.

    Enables domain layer to append events to orchestra log
    without depending on orchestra.logging implementation.
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
        ...
