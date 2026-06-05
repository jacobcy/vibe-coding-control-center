"""vibe3 server module."""

from __future__ import annotations

from typing import TYPE_CHECKING

# Domain layer re-exports (cross-module) - kept minimal
from vibe3.domain import FailedGate, FlowManager

# Runtime layer re-exports (cross-module) - kept minimal
from vibe3.runtime import CircuitBreaker, HeartbeatServer

# Orchestra instance utilities (now in runtime - cross-module) - kept minimal
from vibe3.runtime.orchestra_instance import (
    OrchestraInstanceInfo,
    read_instance_info,
    validate_instance,
    write_instance_info,
)

if TYPE_CHECKING:
    # MCP server
    from vibe3.server.mcp import (
        _serialize_snapshot,
        create_mcp_server,
        format_snapshot_for_mcp,
    )

    # Registry
    from vibe3.server.registry import (
        ORCHESTRA_TMUX_SESSION,
        _build_async_serve_command,
        _build_server,
        _build_server_with_launch_cwd,
        _kill_orchestra_tmux_session,
        _orchestra_tmux_session_exists,
        _resolve_async_cli_override_root,
        _resolve_dispatcher_models_root,
        _resolve_orchestra_log_dir,
        _setup_tailscale_webhook,
        _start_async_serve,
        _validate_pid_file,
    )

    # Server utilities
    from vibe3.server.server_utils import find_available_port

# Lazy imports for self-references (avoid circular init dependencies)
_LAZY_IMPORTS = {
    "create_mcp_server": "vibe3.server.mcp",
    "format_snapshot_for_mcp": "vibe3.server.mcp",
    "_serialize_snapshot": "vibe3.server.mcp",
    "ORCHESTRA_TMUX_SESSION": "vibe3.server.registry",
    "_build_server": "vibe3.server.registry",
    "_build_server_with_launch_cwd": "vibe3.server.registry",
    "_build_async_serve_command": "vibe3.server.registry",
    "_start_async_serve": "vibe3.server.registry",
    "_setup_tailscale_webhook": "vibe3.server.registry",
    "_orchestra_tmux_session_exists": "vibe3.server.registry",
    "_kill_orchestra_tmux_session": "vibe3.server.registry",
    "_resolve_dispatcher_models_root": "vibe3.server.registry",
    "_resolve_orchestra_log_dir": "vibe3.server.registry",
    "_resolve_async_cli_override_root": "vibe3.server.registry",
    "_validate_pid_file": "vibe3.server.registry",
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
    "_serialize_snapshot",
    # registry
    "_validate_pid_file",
    "_build_server",
    "_build_server_with_launch_cwd",
    "_build_async_serve_command",
    "_start_async_serve",
    "_setup_tailscale_webhook",
    "_orchestra_tmux_session_exists",
    "_kill_orchestra_tmux_session",
    "_resolve_dispatcher_models_root",
    "_resolve_orchestra_log_dir",
    "_resolve_async_cli_override_root",
    "ORCHESTRA_TMUX_SESSION",
]
