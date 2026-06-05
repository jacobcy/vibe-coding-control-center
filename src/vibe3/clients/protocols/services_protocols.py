"""Protocol interfaces for services module to resolve circular dependencies.

These protocols define the interfaces that roles and runtime modules need
from services, allowing dependency injection instead of direct imports.
"""

from typing import TYPE_CHECKING, Any, Callable, Protocol

if TYPE_CHECKING:
    from vibe3.exceptions import ErrorSeverity
    from vibe3.models import IssueState


class CheckServiceProtocol(Protocol):
    """Protocol for CheckService used by runtime."""

    def verify_current_flow(self) -> Any:
        """Verify current branch flow consistency."""
        ...

    def verify_branch(self, branch: str) -> Any:
        """Verify a specific branch flow consistency.

        Args:
            branch: Branch name to verify.

        Returns:
            CheckResult with validation status and issues.
        """
        ...

    def verify_all_flows(
        self,
        status: str | list[str] | None = "active",
        on_progress: Callable[[int, int, str], None] | None = None,
    ) -> list[Any]:
        """Run consistency checks for flows in the store.

        Args:
            status: Filter flows by status(es). None checks all flows.
            on_progress: Optional callback invoked after each branch check.

        Returns:
            List of CheckResult objects.
        """
        ...

    def auto_fix(self, issues: list[str], *, branch: str | None = None) -> Any:
        """Auto-fix local consistency issues for a branch.

        Args:
            issues: List of issue descriptions to fix.
            branch: Optional branch name. Defaults to current branch.

        Returns:
            FixResult with success status and applied fixes.
        """
        ...


class FlowServiceProtocol(Protocol):
    """Protocol for FlowService used by runtime."""

    def get_current_branch(self) -> str:
        """Get current git branch.

        Returns:
            Current branch name.
        """
        ...


class ErrorTrackingServiceProtocol(Protocol):
    """Protocol for ErrorTrackingService used by runtime."""

    def record_error(
        self,
        error_code: str,
        error_message: str,
        tick_id: int = 0,
        issue_number: int | None = None,
        branch: str | None = None,
        severity: "ErrorSeverity | None" = None,
    ) -> tuple[bool, int]:
        """Record error and check if threshold reached.

        Args:
            error_code: Error code (E_MODEL_*, E_API_*, E_EXEC_*)
            error_message: Error message/details
            tick_id: Tick ID (defaults to 0)
            issue_number: Optional linked issue
            branch: Optional linked branch
            severity: Optional severity level. If None, inferred from error registry.

        Returns:
            (threshold_reached: bool, error_count_in_window: int)
        """
        ...

    def get_threshold_error_count(self) -> int:
        """Get count of ERROR-severity errors within time window."""
        ...

    def has_critical_error(self) -> bool:
        """Check if there are any CRITICAL severity errors."""
        ...

    def has_model_config_error(self) -> bool:
        """Check if there are any model configuration errors."""
        ...


class ExpiredResourceCleanupServiceProtocol(Protocol):
    """Protocol for ExpiredResourceCleanupService used by runtime."""

    def clean_expired_agent_worktrees(
        self, max_age_days: int = 7, *, quiet: bool = False
    ) -> dict[str, Any]:
        """Clean expired agent worktrees older than max_age_days.

        Args:
            max_age_days: Max age in days before cleanup (default: 7)
            quiet: If True, suppress terminal output (for daemon/heartbeat use)

        Returns:
            Dict with 'cleaned' list and 'skipped_live' list
        """
        ...

    def clean_expired_remote_branches(
        self, max_age_days: int = 30, *, quiet: bool = False
    ) -> dict[str, Any]:
        """Clean expired remote non-protected branches.

        Args:
            max_age_days: Max age in days before cleanup (default: 30)
            quiet: If True, suppress terminal output

        Returns:
            Dict with 'cleaned' list
        """
        ...

    def clean_expired_local_branches(
        self, max_age_days: int = 30, *, quiet: bool = False
    ) -> dict[str, Any]:
        """Clean expired local non-protected branches.

        Args:
            max_age_days: Max age in days before cleanup (default: 30)
            quiet: If True, suppress terminal output

        Returns:
            Dict with 'cleaned' list
        """
        ...


class TriggerableRoleDefinitionProtocol(Protocol):
    """Protocol for TriggerableRoleDefinition used by services.label_utils.

    This protocol captures the essential interface that label_utils needs
    from TriggerableRoleDefinition without requiring direct import of roles module.
    """

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
        """Predicate to determine if role should dispatch.

        Args:
            flow_state: Flow state dict
            has_live_session: Whether there's a live session

        Returns:
            True if should dispatch, False otherwise
        """
        ...


__all__ = [
    "CheckServiceProtocol",
    "FlowServiceProtocol",
    "ErrorTrackingServiceProtocol",
    "ExpiredResourceCleanupServiceProtocol",
    "TriggerableRoleDefinitionProtocol",
]
