"""Core layer protocol interfaces to break circular dependencies.

These protocols break the following circular dependencies:
- FlowServiceProtocol: domain → services
- ExecutionCoordinatorProtocol: domain → execution
- RoleFactoryProtocol: domain → roles

By depending on abstractions (protocols) instead of concrete implementations,
the domain layer avoids circular imports while maintaining type safety.
"""

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from vibe3.models.execution_request import ExecutionRequest
    from vibe3.models.flow import FlowState


@runtime_checkable
class FlowServiceProtocol(Protocol):
    """Protocol for FlowService to break domain → services dependency."""

    def get_flow(self, branch: str) -> "FlowState | None":
        """Get flow by branch."""
        ...

    def update_flow(self, branch: str, **kwargs: object) -> None:
        """Update flow state."""
        ...


@runtime_checkable
class ExecutionCoordinatorProtocol(Protocol):
    """Protocol for ExecutionCoordinator to break domain → execution dependency."""

    def start_execution(self, flow_slug: str, **kwargs: object) -> None:
        """Start execution for a flow."""
        ...

    def stop_execution(self, flow_slug: str) -> None:
        """Stop execution for a flow."""
        ...


@runtime_checkable
class RoleFactoryProtocol(Protocol):
    """Protocol for role factories to break domain → roles dependency."""

    def build_plan_request(self, **kwargs: object) -> "ExecutionRequest":
        """Build plan request."""
        ...

    def build_run_request(self, **kwargs: object) -> "ExecutionRequest":
        """Build run request."""
        ...

    def build_review_request(self, **kwargs: object) -> "ExecutionRequest":
        """Build review request."""
        ...
