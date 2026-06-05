"""Protocol interfaces for orchestra module to resolve circular dependencies.

These protocols define the interfaces that services modules need from orchestra,
allowing dependency injection instead of direct imports.

Critical: These protocols match ACTUAL implementations, not spec guesses.
Verified by reading:
- vibe3.observability.orchestra_log (event logging functions)
- vibe3.domain.failed_gate (FailedGate class)
"""

from pathlib import Path
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from vibe3.clients import SQLiteClient
    from vibe3.domain.failed_gate import GateResult, GateStatus


class OrchestraEventLogProtocol(Protocol):
    """Protocol for orchestra event logging functions.

    Used by services to get log paths and append events without
    importing from observability module directly.
    """

    def __call__(self, repo_root: Path | None = None) -> Path:
        """Get orchestra events log path.

        Args:
            repo_root: Optional repository root path.

        Returns:
            Path to events.log file.
        """
        ...


class AppendGovernanceEventProtocol(Protocol):
    """Protocol for append_governance_event function.

    Used by scan_service to append governance events without
    importing from observability module directly.
    """

    def __call__(self, message: str, *, repo_root: Path | None = None) -> Path:
        """Append a governance event to logs.

        Args:
            message: Event message to append.
            repo_root: Optional repository root path.

        Returns:
            Path to governance.log file.
        """
        ...


class FailedGateProtocol(Protocol):
    """Protocol for FailedGate used by serve_status_service.

    Allows services to check gate status without importing from
    domain.failed_gate directly.
    """

    def __init__(self, store: "SQLiteClient | None" = None) -> None:
        """Initialize FailedGate with optional SQLite persistence.

        Args:
            store: SQLiteClient for database access.
        """
        ...

    def check(self) -> "GateResult":
        """Check if orchestra dispatch should be frozen.

        Returns:
            GateResult with blocked status and reason.
        """
        ...

    def get_status(self) -> "GateStatus":
        """Get full gate status for display.

        Returns:
            GateStatus dataclass with all fields.
        """
        ...


__all__ = [
    "OrchestraEventLogProtocol",
    "AppendGovernanceEventProtocol",
    "FailedGateProtocol",
]
