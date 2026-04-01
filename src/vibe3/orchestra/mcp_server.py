"""Shim for vibe3.orchestra.mcp_server - moved to vibe3.server.mcp."""

from vibe3.server.mcp import (
    _serialize_snapshot,
    create_mcp_server,
    format_snapshot_for_mcp,
)

__all__ = ["create_mcp_server", "format_snapshot_for_mcp", "_serialize_snapshot"]
