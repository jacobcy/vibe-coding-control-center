"""vibe3 server module."""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    # Domain layer re-exports
    from vibe3.domain import FailedGate, FlowManager

    # Runtime layer re-exports
    from vibe3.runtime import CircuitBreaker, HeartbeatServer

    # Orchestra instance utilities (now in runtime)
    from vibe3.runtime.orchestra_instance import (
        OrchestraInstanceInfo,
        read_instance_info,
        validate_instance,
        write_instance_info,
    )

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


def __getattr__(name: str) -> Any:
    """Lazy import for all symbols to avoid circular dependencies."""
    # Domain layer re-exports
    if name == "FailedGate":
        from vibe3.domain import FailedGate

        return FailedGate
    if name == "FlowManager":
        from vibe3.domain import FlowManager

        return FlowManager

    # Runtime layer re-exports
    if name == "CircuitBreaker":
        from vibe3.runtime import CircuitBreaker

        return CircuitBreaker
    if name == "HeartbeatServer":
        from vibe3.runtime import HeartbeatServer

        return HeartbeatServer

    # Orchestra instance utilities
    if name == "OrchestraInstanceInfo":
        from vibe3.runtime.orchestra_instance import OrchestraInstanceInfo

        return OrchestraInstanceInfo
    if name == "read_instance_info":
        from vibe3.runtime.orchestra_instance import read_instance_info

        return read_instance_info
    if name == "validate_instance":
        from vibe3.runtime.orchestra_instance import validate_instance

        return validate_instance
    if name == "write_instance_info":
        from vibe3.runtime.orchestra_instance import write_instance_info

        return write_instance_info

    # MCP server
    if name == "_serialize_snapshot":
        from vibe3.server.mcp import _serialize_snapshot

        return _serialize_snapshot
    if name == "create_mcp_server":
        from vibe3.server.mcp import create_mcp_server

        return create_mcp_server
    if name == "format_snapshot_for_mcp":
        from vibe3.server.mcp import format_snapshot_for_mcp

        return format_snapshot_for_mcp

    # Registry
    if name == "ORCHESTRA_TMUX_SESSION":
        from vibe3.server.registry import ORCHESTRA_TMUX_SESSION

        return ORCHESTRA_TMUX_SESSION
    if name == "_build_async_serve_command":
        from vibe3.server.registry import _build_async_serve_command

        return _build_async_serve_command
    if name == "_build_server":
        from vibe3.server.registry import _build_server

        return _build_server
    if name == "_build_server_with_launch_cwd":
        from vibe3.server.registry import _build_server_with_launch_cwd

        return _build_server_with_launch_cwd
    if name == "_kill_orchestra_tmux_session":
        from vibe3.server.registry import _kill_orchestra_tmux_session

        return _kill_orchestra_tmux_session
    if name == "_orchestra_tmux_session_exists":
        from vibe3.server.registry import _orchestra_tmux_session_exists

        return _orchestra_tmux_session_exists
    if name == "_resolve_async_cli_override_root":
        from vibe3.server.registry import _resolve_async_cli_override_root

        return _resolve_async_cli_override_root
    if name == "_resolve_dispatcher_models_root":
        from vibe3.server.registry import _resolve_dispatcher_models_root

        return _resolve_dispatcher_models_root
    if name == "_resolve_orchestra_log_dir":
        from vibe3.server.registry import _resolve_orchestra_log_dir

        return _resolve_orchestra_log_dir
    if name == "_setup_tailscale_webhook":
        from vibe3.server.registry import _setup_tailscale_webhook

        return _setup_tailscale_webhook
    if name == "_start_async_serve":
        from vibe3.server.registry import _start_async_serve

        return _start_async_serve
    if name == "_validate_pid_file":
        from vibe3.server.registry import _validate_pid_file

        return _validate_pid_file

    # Server utilities
    if name == "find_available_port":
        from vibe3.server.server_utils import find_available_port

        return find_available_port

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
