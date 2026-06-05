"""Utility modules for Vibe3."""

from __future__ import annotations

from typing import TYPE_CHECKING

# Cross-module imports (not self-references)
from vibe3.clients.runtime_assets import (
    resolve_prompt_config,
    resolve_runtime_asset,
    runtime_assets_root,
)

if TYPE_CHECKING:
    from vibe3.utils.codeagent_helpers import (
        build_prompt_file_content,
        diagnose_backend_error,
        prepare_prompt_file,
        sanitize_prompt_for_display,
        sanitize_task_shell_meta,
        stream_reader,
        summarize_backend_output,
    )
    from vibe3.utils.constants import (
        AUTOMATED_MARKERS,
        GENERIC_AGENT_MARKER_PATTERN,
        STARTING_TIMEOUT_SECONDS,
    )

# Lazy imports
_LAZY_IMPORTS = {
    "build_prompt_file_content": "vibe3.utils.codeagent_helpers",
    "diagnose_backend_error": "vibe3.utils.codeagent_helpers",
    "prepare_prompt_file": "vibe3.utils.codeagent_helpers",
    "sanitize_prompt_for_display": "vibe3.utils.codeagent_helpers",
    "sanitize_task_shell_meta": "vibe3.utils.codeagent_helpers",
    "stream_reader": "vibe3.utils.codeagent_helpers",
    "summarize_backend_output": "vibe3.utils.codeagent_helpers",
    "AUTOMATED_MARKERS": "vibe3.utils.constants",
    "GENERIC_AGENT_MARKER_PATTERN": "vibe3.utils.constants",
    "STARTING_TIMEOUT_SECONDS": "vibe3.utils.constants",
}


def __getattr__(name: str) -> object:
    """Lazy import for utils symbols to avoid circular dependencies."""
    if name in _LAZY_IMPORTS:
        import importlib

        module = importlib.import_module(_LAZY_IMPORTS[name])
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "AUTOMATED_MARKERS",
    "GENERIC_AGENT_MARKER_PATTERN",
    "STARTING_TIMEOUT_SECONDS",
    "build_prompt_file_content",
    "diagnose_backend_error",
    "prepare_prompt_file",
    "resolve_prompt_config",
    "resolve_runtime_asset",
    "runtime_assets_root",
    "sanitize_prompt_for_display",
    "sanitize_task_shell_meta",
    "stream_reader",
    "summarize_backend_output",
]
