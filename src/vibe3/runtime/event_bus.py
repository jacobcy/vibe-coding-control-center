"""Event bus for orchestra: event model and service base class."""

from abc import ABC, abstractmethod
from typing import Any, Literal

from pydantic import BaseModel


class GitHubEvent(BaseModel):
    """Normalised GitHub event from webhook or polling."""

    event_type: str
    """GitHub event type: 'issues', 'pull_request', 'issue_comment', etc."""

    action: str
    """GitHub event action: 'assigned', 'created', 'opened', etc."""

    payload: dict[str, Any]
    """Raw GitHub webhook payload."""

    source: Literal["webhook", "poll"] = "poll"
    """Origin of the event."""


class ServiceBase(ABC):
    """Abstract base for all orchestra services.

    Subclasses declare which event_types they handle and implement
    handle_event(). They may also override on_tick() for polling behaviour.
    """

    event_types: list[str] = []
    """GitHub event types this service subscribes to."""

    @property
    def service_name(self) -> str:
        """Human-readable service name for orchestration logs."""
        return type(self).__name__

    @property
    def is_dispatch_service(self) -> bool:
        """Whether this service initiates automated flow/task actions.

        True for dispatchers that push the flow forward (manager/run/review).
        False for non-dispatching services like comment replies.
        """
        return True

    @abstractmethod
    async def handle_event(self, event: GitHubEvent) -> None:
        """React to a GitHub event."""
        ...

    async def on_tick(self) -> None:
        """Called on each heartbeat tick (every polling_interval seconds).

        Override to add polling-based behaviour as a fallback.
        The default implementation is a no-op.
        """
