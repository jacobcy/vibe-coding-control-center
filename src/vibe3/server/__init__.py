"""vibe3 server module."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # Domain layer re-exports
    from vibe3.domain import FailedGate, FlowManager

    # Runtime layer re-exports
    # Orchestra instance utilities (now in runtime)
    from vibe3.runtime import (
        CircuitBreaker,
        HeartbeatServer,
        OrchestraInstanceInfo,
        read_instance_info,
        validate_instance,
        write_instance_info,
    )

    # MCP server
    from vibe3.server.mcp import (
        create_mcp_server,
        format_snapshot_for_mcp,
    )

    # Server utilities
    from vibe3.server.server_utils import find_available_port

# Lazy imports for all symbols (avoid circular init dependencies)
_LAZY_IMPORTS = {
    # Domain layer re-exports
    "FailedGate": "vibe3.domain",
    "FlowManager": "vibe3.domain",
    # Runtime layer re-exports
    "CircuitBreaker": "vibe3.runtime",
    "HeartbeatServer": "vibe3.runtime",
    # Orchestra instance utilities
    "OrchestraInstanceInfo": "vibe3.runtime",
    "read_instance_info": "vibe3.runtime",
    "validate_instance": "vibe3.runtime",
    "write_instance_info": "vibe3.runtime",
    # MCP server
    "create_mcp_server": "vibe3.server.mcp",
    "format_snapshot_for_mcp": "vibe3.server.mcp",
    # Server utilities
    "find_available_port": "vibe3.server.server_utils",
}


def __getattr__(name: str) -> object:
    """Lazy import for server symbols to avoid circular dependencies."""
    if name in _LAZY_IMPORTS:
        import importlib

        module = importlib.import_module(_LAZY_IMPORTS[name])
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    # domain
    "FailedGate",
    "FlowManager",
    # runtime
    "CircuitBreaker",
    "HeartbeatServer",
    # orchestra_instance
    "OrchestraInstanceInfo",
    "read_instance_info",
    "write_instance_info",
    "validate_instance",
    # server_utils
    "find_available_port",
    # mcp
    "create_mcp_server",
    "format_snapshot_for_mcp",
]
