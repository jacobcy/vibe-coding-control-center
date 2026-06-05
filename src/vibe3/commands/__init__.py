"""Commands package."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from vibe3.server.registry import _validate_pid_file


def __getattr__(name: str) -> Any:
    """Lazy import for symbols to avoid cross-module import cascades."""
    if name == "_validate_pid_file":
        from vibe3.server.registry import _validate_pid_file

        globals()["_validate_pid_file"] = _validate_pid_file
        return _validate_pid_file

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "check",
    "flow",
    "handoff",
    "inspect",
    "plan",
    "pr",
    "review",
    "run",
    "snapshot",
    "_validate_pid_file",
]
