"""Shim for vibe3.orchestra.serve_utils - moved to vibe3.server.registry."""

from vibe3.server.registry import (
    _build_async_serve_command,
    _build_server,
    _is_orchestra_process,
    _resolve_tsu_script,
    _setup_tailscale_webhook,
    _start_async_serve,
    _validate_pid_file,
)

__all__ = [
    "_build_server",
    "_resolve_tsu_script",
    "_setup_tailscale_webhook",
    "_is_orchestra_process",
    "_validate_pid_file",
    "_build_async_serve_command",
    "_start_async_serve",
]
