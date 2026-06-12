"""Protocol definitions for dispatch coordination."""

from typing import TYPE_CHECKING, Callable, Protocol

if TYPE_CHECKING:
    from vibe3.clients import GitHubClient, SQLiteClient
    from vibe3.domain.qualify_gate import QualifyGateService
    from vibe3.models import IssueInfo, IssueState, OrchestraConfig, QueueEntry
    from vibe3.services import CheckResult

    from .flow_protocols import FlowManagerProtocol


class IssueCollectionServiceProtocol(Protocol):
    """Protocol for issue collection service."""

    def collect_open_issues(self, limit: int = 100) -> list["IssueInfo"]:
        """Collect open issues from GitHub.

        Args:
            limit: Maximum number of issues to collect

        Returns:
            List of normalized IssueInfo objects
        """
        ...


class QueuePersistenceServiceProtocol(Protocol):
    """Protocol for queue persistence."""

    frozen_queue: list["QueueEntry"] | None

    def persist(self) -> None:
        """Persist queue state."""
        ...

    def restore(self) -> list["QueueEntry"] | None:
        """Restore queue state.

        Returns:
            Restored queue entries or None
        """
        ...

    def get_queued_issue_numbers(self) -> set[int]:
        """Get the set of issue numbers currently in the frozen queue.

        Returns:
            Set of issue numbers in queue
        """
        ...

    def promote(self) -> bool:
        """Move progressed issues to the front; remove blocked/failed from queue.

        Returns:
            True if all entries were removed (queue cleared), False otherwise.
        """
        ...


class IssueLoaderProtocol(Protocol):
    """Protocol for loading issue snapshots."""

    def __call__(self, issue_number: int) -> "IssueInfo | None":
        """Load issue snapshot.

        Args:
            issue_number: Issue number to load

        Returns:
            IssueInfo if found, None otherwise
        """
        ...


class FlowContextResolverProtocol(Protocol):
    """Protocol for resolving flow context (branch, state) for an issue."""

    def __call__(self, issue_number: int) -> tuple[str, dict[str, object] | None]:
        """Resolve flow context for an issue.

        Args:
            issue_number: Issue number to resolve

        Returns:
            Tuple of (branch_name, flow_state_dict or None)
        """
        ...


class QueueSelectorProtocol(Protocol):
    """Protocol for selecting ready issues from collected issues."""

    def __call__(
        self,
        issues: list["IssueInfo"],
        trigger_state: "IssueState",
        config: "OrchestraConfig",
        github: "GitHubClient",
        store: "SQLiteClient",
        flow_manager: "FlowManagerProtocol",
        qualify_gate: "QualifyGateService",
        supervisor_label: str,
        *,
        role_resolver: Callable[["IssueState"], object | None] | None = None,
        queue_filter: Callable[..., bool] | None = None,
        label_service: object | None = None,
    ) -> list["IssueInfo"]:
        """Select ready issues from collected issues.

        Args:
            issues: Collected issues
            trigger_state: Target state to filter for
            config: Orchestra config
            github: GitHub client
            store: SQLite client
            flow_manager: Flow manager
            qualify_gate: Qualify gate service
            supervisor_label: Supervisor label

        Returns:
            List of issues ready for the target state
        """
        ...


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


class LabelDispatchCallable(Protocol):
    """Protocol for label dispatch event builder callable."""

    def __call__(
        self,
        role: object,  # TriggerableRoleDefinition (avoid importing from roles)
        issue: "IssueInfo",
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


class TriggerableRoleDefinitionProtocol(Protocol):
    """Protocol for TriggerableRoleDefinition used by services.label_utils."""

    @property
    def trigger_name(self) -> str:
        """Trigger name for this role (e.g., 'manager', 'plan', 'run')."""
        ...

    @property
    def trigger_state(self) -> "IssueState":
        """Issue state that triggers this role (e.g., IssueState.READY)."""
        ...

    @property
    def dispatch_predicate(self) -> Callable[[dict[str, object], bool], bool]:
        """Predicate to determine if role should dispatch."""
        ...
