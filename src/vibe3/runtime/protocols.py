"""Runtime service protocols.

Canonical home for ServiceBase and CheckServiceProtocol.
Domain and orchestra layers re-export from here for backward compatibility.
"""

from __future__ import annotations

from abc import ABC
from typing import TYPE_CHECKING, Callable, Protocol

if TYPE_CHECKING:
    from vibe3.models import CheckResult


class ServiceBase(ABC):
    """Abstract protocol for runtime services observed by HeartbeatServer."""

    @property
    def service_name(self) -> str:
        """Human-readable service name for orchestration logs."""
        return type(self).__name__

    @property
    def is_dispatch_service(self) -> bool:
        """Whether this service initiates automated flow/task actions."""
        return True

    async def on_tick(self, tick_id: int = 0) -> None:
        """Called on each heartbeat tick."""
        ...


class CheckServiceProtocol(Protocol):
    """Protocol for health check service operations."""

    def verify_current_flow(self) -> "CheckResult":
        """Verify current branch flow consistency."""
        ...

    def verify_branch(self, branch: str) -> "CheckResult":
        """Verify branch flow consistency.

        Args:
            branch: Branch name to verify

        Returns:
            CheckResult with validation status and issues/warnings
        """
        ...

    def verify_all_flows(
        self,
        status: str | list[str] | None = "active",
        on_progress: Callable[[int, int, str], None] | None = None,
    ) -> list["CheckResult"]:
        """Run consistency checks for flows in the store."""
        ...

    def invalidate_pr_cache(self) -> None:
        """Invalidate PR cache to force refresh on next check."""
        ...

    def clean_orchestra_scanned_with_assignee(self) -> int:
        """Remove orchestra-scanned label from issues with assignee.

        Returns:
            Number of issues cleaned.
        """
        ...

    def enforce_label_constraints_remote(self) -> int:
        """Scan remote open issues for label constraint violations and auto-fix.

        Returns:
            Number of issues with violations fixed.
        """
        ...
