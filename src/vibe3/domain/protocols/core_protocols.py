"""Core layer protocol interfaces to break circular dependencies."""

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class FlowServiceProtocol(Protocol):
    """Protocol for FlowService to break domain → services dependency."""

    def get_flow(self, branch: str) -> Any:
        """Get flow by branch."""
        ...

    def update_flow(self, branch: str, **kwargs: Any) -> None:
        """Update flow state."""
        ...


@runtime_checkable
class ExecutionCoordinatorProtocol(Protocol):
    """Protocol for ExecutionCoordinator to break domain → execution dependency."""

    def start_execution(self, flow_slug: str, **kwargs: Any) -> None:
        """Start execution for a flow."""
        ...

    def stop_execution(self, flow_slug: str) -> None:
        """Stop execution for a flow."""
        ...


@runtime_checkable
class RoleFactoryProtocol(Protocol):
    """Protocol for role factories to break domain → roles dependency."""

    def build_plan_request(self, **kwargs: Any) -> Any:
        """Build plan request."""
        ...

    def build_run_request(self, **kwargs: Any) -> Any:
        """Build run request."""
        ...

    def build_review_request(self, **kwargs: Any) -> Any:
        """Build review request."""
        ...
