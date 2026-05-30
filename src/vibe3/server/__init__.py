"""vibe3 server module."""

# Orchestra instance utilities
# MCP server
from vibe3.server.mcp import (
    _serialize_snapshot,
    create_mcp_server,
    format_snapshot_for_mcp,
)
from vibe3.server.orchestra_instance import (
    OrchestraInstanceInfo,
    read_instance_info,
    validate_instance,
    write_instance_info,
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

__all__ = [
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
