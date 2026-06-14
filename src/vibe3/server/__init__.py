"""vibe3 server module."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # MCP server
    from vibe3.server.mcp import (
        create_mcp_server,
        format_snapshot_for_mcp,
    )

    # Server utilities
    from vibe3.server.server_utils import find_available_port

    # Registry (public API) - re-exported from utils
    from vibe3.utils import validate_pid_file

# Lazy imports for all symbols (avoid circular init dependencies)
_LAZY_IMPORTS = {
    # MCP server
    "create_mcp_server": "vibe3.server.mcp",
    "format_snapshot_for_mcp": "vibe3.server.mcp",
    # Server utilities
    "find_available_port": "vibe3.server.server_utils",
    # Registry (public API)
    "validate_pid_file": "vibe3.utils",
}


def __getattr__(name: str) -> object:
    """Lazy import for server symbols to avoid circular dependencies."""
    if name in _LAZY_IMPORTS:
        import importlib

        module = importlib.import_module(_LAZY_IMPORTS[name])
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    # server_utils
    "find_available_port",
    # mcp
    "create_mcp_server",
    "format_snapshot_for_mcp",
    # registry (public API)
    "validate_pid_file",
]
