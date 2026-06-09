"""Protocol definitions for Orchestra layer dependency injection.

These protocols define the interfaces required by GlobalDispatchCoordinator,
allowing it to depend on abstractions rather than concrete service implementations.
This breaks the orchestra→services/execution/roles circular dependency chain.

Note: Most protocols have been migrated to domain layer (dispatch_protocols.py).
The definitions below are maintained for backward compatibility during migration.
"""

from typing import Protocol

from vibe3.clients import GitClient
from vibe3.models import IssueInfo

# Re-export protocols from orchestra.domain_types (KERNEL) for backward compatibility
from vibe3.orchestra.domain_types import (
    CapacityServiceProtocol,
    CheckServiceProtocol,
    FlowServiceProtocol,
    LabelDispatchCallable,
)

__all__ = [
    "CapacityServiceProtocol",
    "CheckServiceProtocol",
    "FlowServiceProtocol",
    "LabelDispatchCallable",
    "IssueCollectionServiceProtocol",
    "FlowManagerProtocol",
]


class IssueCollectionServiceProtocol(Protocol):
    """Protocol for issue collection service operations."""

    def collect_open_issues(self, limit: int = 100) -> list[IssueInfo]:
        """Collect open GitHub issues."""
        ...


class FlowManagerProtocol(Protocol):
    """Protocol for flow manager operations (external consumer interface)."""

    git: GitClient

    def get_flow_for_issue(self, issue_number: int) -> dict | None:
        """Find the latest flow for an issue."""
        ...

    def create_flow_for_issue(self, issue: IssueInfo) -> dict | None:
        """Create or reuse a flow for an issue."""
        ...

    def resolve_best_flow(self, issue_number: int, flows: list[dict]) -> dict | None:
        """Resolve best flow from pre-fetched list."""
        ...
