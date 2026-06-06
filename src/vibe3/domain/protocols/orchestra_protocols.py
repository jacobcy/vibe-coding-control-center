"""Protocol interfaces for orchestra module to resolve circular dependencies.

These protocols define the interfaces that services modules need from orchestra,
allowing dependency injection instead of direct imports.
"""

from pathlib import Path
from typing import Protocol

from vibe3.domain.failed_gate import GateResult, GateStatus


class OrchestraEventLogProtocol(Protocol):
    """Protocol for orchestra event logging functions."""

    def __call__(self, repo_root: Path | None = None) -> Path:
        """Get orchestra events log path."""
        ...


class AppendGovernanceEventProtocol(Protocol):
    """Protocol for append_governance_event function."""

    def __call__(self, message: str, *, repo_root: Path | None = None) -> Path:
        """Append a governance event to logs."""
        ...


class FailedGateProtocol(Protocol):
    """Protocol for FailedGate used by serve_status_service."""

    def check(self) -> GateResult:
        """Check if orchestra dispatch should be frozen."""
        ...

    def get_status(self) -> GateStatus:
        """Get full gate status for display."""
        ...


__all__ = [
    "AppendGovernanceEventProtocol",
    "FailedGateProtocol",
    "OrchestraEventLogProtocol",
]
