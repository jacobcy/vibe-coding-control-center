"""Runtime layer protocol interfaces.

Moved from runtime/service_protocol.py to domain/protocols/ to break
domain→runtime circular dependency. Domain can now import ServiceBase
without depending on the runtime layer.
"""

from abc import ABC


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
        """Called on each heartbeat tick.

        Args:
            tick_id: Current tick number (0 if not available)
        """
