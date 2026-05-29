"""Protocol definitions for Orchestra layer dependency injection.

These protocols define the interfaces required by GlobalDispatchCoordinator,
allowing it to depend on abstractions rather than concrete service implementations.
This breaks the orchestra→services/execution/roles circular dependency chain.
"""

from typing import Protocol

from vibe3.clients.git_client import GitClient
from vibe3.models.orchestration import IssueInfo
from vibe3.services.check_service import CheckResult


class CapacityServiceProtocol(Protocol):
    """Protocol for capacity service operations."""

    def get_capacity_status(self, role: str) -> dict[str, int]:
        """Get current capacity status.

        Args:
            role: Role name for logging/context

        Returns:
            Dict with capacity metrics (e.g., {"remaining": int, "active": int})
        """
        ...


class CheckServiceProtocol(Protocol):
    """Protocol for health check service operations."""

    def verify_branch(self, branch: str) -> CheckResult:
        """Verify branch flow consistency.

        Args:
            branch: Branch name to verify

        Returns:
            CheckResult with validation status and issues/warnings
        """
        ...

    def invalidate_pr_cache(self) -> None:
        """Invalidate PR cache to force refresh on next check.

        Should be called when:
        - Queue is restored from persistence
        - Queue is cleared after promote()
        - Fresh queue collection occurs
        """
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
        """Mark flow as blocked.

        Args:
            branch: Branch name
            reason: Blocking reason
            blocked_by_issue: Dependency issue number
            actor: Actor performing the block
            repo: Repository (defaults to current repo)
            event_type: Event type for timeline
        """
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


class FlowManagerProtocol(Protocol):
    """Protocol for flow manager operations (external consumer interface).

    This protocol exposes only the methods used by external consumers,
    not the internal service dependencies of FlowManager.
    """

    git: GitClient

    def get_flow_for_issue(self, issue_number: int) -> dict | None:
        """Find the latest flow for an issue.

        Args:
            issue_number: GitHub issue number

        Returns:
            Flow dict if found, None otherwise
        """
        ...

    def create_flow_for_issue(self, issue: IssueInfo) -> dict | None:
        """Create or reuse a flow for an issue.

        Args:
            issue: IssueInfo object

        Returns:
            Flow dict if created/reused, None on failure
        """
        ...


class LabelDispatchCallable(Protocol):
    """Protocol for label dispatch event builder callable."""

    def __call__(
        self,
        role: object,  # TriggerableRoleDefinition (avoid importing from roles)
        issue: IssueInfo,
        *,
        branch: str,
        tick_id: int = 0,
    ) -> object:  # DispatchIntent union type (avoid importing from domain)
        """Build dispatch intent event for a role.

        Args:
            role: Triggerable role definition
            issue: Issue info
            branch: Branch name
            tick_id: Heartbeat tick number

        Returns:
            DispatchIntent event object
        """
        ...
