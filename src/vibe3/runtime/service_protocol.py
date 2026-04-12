"""Service protocol for runtime observers.

This module defines the GitHub-facing observation model and the minimal runtime
service contract used by HeartbeatServer.
"""

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
    """Abstract protocol for runtime services observed by HeartbeatServer."""

    event_types: list[str] = []
    """GitHub event types this service subscribes to."""

    @property
    def service_name(self) -> str:
        """Human-readable service name for orchestration logs."""
        return type(self).__name__

    @property
    def is_dispatch_service(self) -> bool:
        """Whether this service initiates automated flow/task actions."""
        return True

    @abstractmethod
    async def handle_event(self, event: GitHubEvent) -> None:
        """React to a GitHub event."""
        ...

    async def on_tick(self) -> None:
        """Called on each heartbeat tick."""
