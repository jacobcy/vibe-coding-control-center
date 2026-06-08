"""Domain types and protocols for the KERNEL layer.

This module is the canonical home for protocol definitions and value types
used by KERNEL modules (orchestra, runtime). These definitions are relocated
from the domain layer to break the dependency direction violation where
KERNEL imports from OBSERVATION.

KERNEL modules must import from this module instead of from vibe3.domain.
"""

from __future__ import annotations

from abc import ABC
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Protocol

if TYPE_CHECKING:
    from vibe3.clients import GitClient
    from vibe3.models import IssueInfo, IssueState


# ---- Value Types ----


@dataclass(frozen=True)
class GateResult:
    """Result of a failed gate check."""

    blocked: bool
    reason: str | None = None
    blocked_ticks: int = 0

    @classmethod
    def open_gate(cls) -> GateResult:
        """Create a non-blocking gate result."""
        return cls(blocked=False)


@dataclass
class GateStatus:
    """Full status of FailedGate for display."""

    is_active: bool
    reason: str | None
    triggered_at: str | None
    triggered_by_error_code: str | None
    cleared_at: str | None
    cleared_by: str | None
    cleared_reason: str | None
    blocked_ticks: int


class CheckResultProtocol(Protocol):
    """Protocol for check result objects."""

    @property
    def is_valid(self) -> bool:
        """Whether the check passed."""
        ...

    @property
    def issues(self) -> list[str]:
        """List of issues found."""
        ...

    @property
    def warnings(self) -> list[str]:
        """List of warnings."""
        ...


# ---- Service Protocols ----


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


class CapacityServiceProtocol(Protocol):
    """Protocol for capacity service operations."""

    def get_capacity_status(self, role: str) -> dict[str, int]:
        """Get current capacity status.

        Args:
            role: Role name for logging/context

        Returns:
            Dict with capacity metrics
        """
        ...


class CheckServiceProtocol(Protocol):
    """Protocol for health check service operations."""

    def verify_current_flow(self) -> CheckResultProtocol:
        """Verify current branch flow consistency."""
        ...

    def verify_branch(self, branch: str) -> CheckResultProtocol:
        """Verify branch flow consistency."""
        ...

    def verify_all_flows(
        self,
        status: str | list[str] | None = "active",
        on_progress: Callable[[int, int, str], None] | None = None,
    ) -> list[CheckResultProtocol]:
        """Run consistency checks for flows in the store."""
        ...

    def invalidate_pr_cache(self) -> None:
        """Invalidate PR cache to force refresh on next check."""
        ...


class FlowServiceProtocol(Protocol):
    """Protocol for flow service lifecycle operations."""

    def block_flow(
        self,
        branch: str,
        reason: str | None = None,
        blocked_by_issue: int | None = None,
        actor: str | None = None,
        repo: str | None = None,
        event_type: str = "flow_blocked",
    ) -> None:
        """Mark flow as blocked."""
        ...


class LabelDispatchCallable(Protocol):
    """Protocol for label dispatch event builder callable."""

    def __call__(
        self,
        role: object,
        issue: IssueInfo,
        *,
        branch: str,
        tick_id: int = 0,
    ) -> object:
        """Build dispatch intent event for a role."""
        ...


class FlowManagerProtocol(Protocol):
    """Protocol for flow manager operations (external consumer interface).

    This protocol exposes only the methods used by external consumers,
    not the internal service dependencies of FlowManager.
    """

    git: GitClient

    def get_flow_for_issue(self, issue_number: int) -> dict | None:
        """Find the latest flow for an issue."""
        ...

    def create_flow_for_issue(self, issue: IssueInfo) -> dict | None:
        """Create a new flow for an issue."""
        ...


class IssueCollectionServiceProtocol(Protocol):
    """Protocol for issue collection service operations."""

    def collect_open_issues(self, limit: int = 100) -> list[IssueInfo]:
        """Collect open GitHub issues.

        Args:
            limit: Maximum number of issues to collect

        Returns:
            List of normalized IssueInfo objects
        """
        ...


class CleanupServiceProtocol(Protocol):
    """Protocol for expired resource cleanup service."""

    def clean_expired_agent_worktrees(
        self, max_age_days: int, quiet: bool = False
    ) -> dict[str, object]:
        """Clean expired agent worktrees."""
        ...

    def clean_expired_local_branches(
        self, max_age_days: int = 0, *, force: bool = False, quiet: bool = False
    ) -> dict[str, object]:
        """Clean expired local branches."""
        ...

    def clean_expired_remote_branches(
        self, max_age_days: int, quiet: bool = False
    ) -> dict[str, object]:
        """Clean expired remote branches."""
        ...


class LabelServiceProtocol(Protocol):
    """Protocol for label/transition service operations."""

    def transition(
        self,
        issue_number: int,
        target_state: IssueState,
        actor: str = "system",
        force: bool = False,
    ) -> None:
        """Transition issue to target state via label."""
        ...


class QualifyGateServiceProtocol(Protocol):
    """Protocol for qualify gate service operations."""

    def run_qualify_gate(
        self,
        issue: IssueInfo,
        branch: str,
        flow_state: dict[str, object] | None,
        labels: list[str],
        trigger_state: IssueState,
        truth: object | None = None,
    ) -> IssueState | None:
        """Run the Qualify Gate for an issue."""
        ...


__all__ = [
    "GateResult",
    "GateStatus",
    "CheckResultProtocol",
    "ServiceBase",
    "CapacityServiceProtocol",
    "CheckServiceProtocol",
    "FlowServiceProtocol",
    "LabelDispatchCallable",
    "FlowManagerProtocol",
    "IssueCollectionServiceProtocol",
    "CleanupServiceProtocol",
    "LabelServiceProtocol",
    "QualifyGateServiceProtocol",
]
