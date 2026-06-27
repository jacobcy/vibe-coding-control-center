"""Protocol interfaces for role functions injected into execution runners.

These protocols define the contracts for dependency injection,
allowing execution layer to depend on abstractions rather than concrete
role implementations.
"""

from __future__ import annotations

from typing import Any, Callable, Protocol, runtime_checkable

# Import SessionRole from canonical source instead of redefining
from vibe3.models import SessionRole


@runtime_checkable
class GovernanceFunctions(Protocol):
    """Protocol for governance role functions injected into runners."""

    def build_snapshot_context(
        self,
        snapshot: Any,
        *,
        config: Any = None,
        tick_count: int = 0,
        material_override: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Build snapshot context for governance execution."""
        ...

    def render_prompt(
        self,
        config: Any,
        snapshot_context: dict[str, Any],
        *,
        tick_count: int = 0,
        material_override: str | None = None,
        **kwargs: Any,
    ) -> Any:
        """Render governance prompt from snapshot context."""
        ...

    def resolve_options(self, config: Any) -> Any:
        """Resolve agent options for governance execution."""
        ...

    def build_execution_name(self, tick_count: int, material: str | None = None) -> str:
        """Build execution name for governance run."""
        ...


@runtime_checkable
class GovernanceEventLogger(Protocol):
    """Protocol for governance event logging."""

    def __call__(self, message: str, *, repo_root: Any = None) -> Any:
        """Log a governance event."""
        ...


@runtime_checkable
class IssueRoleSyncSpec(Protocol):
    """Protocol for issue-scoped role sync spec.

    Moved from roles.definitions to eliminate execution→roles dependency.
    Concrete dataclass in roles.definitions satisfies this structurally.

    Attributes are declared as read-only properties to match frozen dataclass
    semantics (the concrete implementation uses @dataclass(frozen=True)).
    """

    @property
    def role_name(self) -> SessionRole: ...

    @property
    def resolve_options(self) -> Callable[[Any, dict[str, str] | None], Any]: ...

    @property
    def resolve_branch(self) -> Callable[[Any, int, str], str]: ...

    @property
    def build_async_request(self) -> Callable[[Any, Any, str, str], Any | None]: ...

    @property
    def build_sync_request(self) -> Callable[..., Any]: ...

    @property
    def failure_handler(self) -> Callable[..., None] | None: ...
