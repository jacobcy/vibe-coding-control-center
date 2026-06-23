"""Commands package."""

from __future__ import annotations

from typing import TYPE_CHECKING

# Lazy import mapping for command submodules
_SYMBOL_MODULES = {
    "ask": "vibe3.commands.ask",
    "check": "vibe3.commands.check",
    "feedback": "vibe3.commands.feedback",
    "flow": "vibe3.commands.flow",
    "handoff": "vibe3.commands.handoff",
    "inspect": "vibe3.commands.inspect",
    "plan": "vibe3.commands.plan",
    "pr": "vibe3.commands.pr",
    "review": "vibe3.commands.review",
    "run": "vibe3.commands.run",
    "snapshot": "vibe3.commands.snapshot",
}

# Lazy import mapping for function re-exports from submodules
_SOURCE_SYMBOLS: dict[str, str] = {
    "suggest_next_step": "vibe3.commands.inspect_helpers",
    "render_blocked_items": "vibe3.commands.status_render",
    "render_completed_flows": "vibe3.commands.status_render",
    "render_epic_items": "vibe3.commands.status_render",
    "render_human_collab_flows": "vibe3.commands.status_render",
    "render_issue_progress": "vibe3.commands.status_render",
    "render_missing_state_items": "vibe3.commands.status_render",
    "render_pr_ref_items": "vibe3.commands.status_render",
    "render_remote_items": "vibe3.commands.status_render",
    "render_rfc_items": "vibe3.commands.status_render",
    "render_supervisor_issues": "vibe3.commands.status_render",
}

if TYPE_CHECKING:
    from vibe3.commands.inspect_helpers import suggest_next_step
    from vibe3.commands.status_render import (
        render_blocked_items,
        render_completed_flows,
        render_epic_items,
        render_human_collab_flows,
        render_issue_progress,
        render_missing_state_items,
        render_pr_ref_items,
        render_remote_items,
        render_rfc_items,
        render_supervisor_issues,
    )


def _resolve_symbol(name: str) -> object:
    """Resolve a function or class re-export from a submodule."""
    import importlib

    module_name = _SOURCE_SYMBOLS[name]
    module = importlib.import_module(module_name)
    symbol = getattr(module, name)
    globals()[name] = symbol
    return symbol


def __getattr__(name: str) -> object:
    """Lazy import for command submodules and function re-exports."""
    if name in _SOURCE_SYMBOLS:
        return _resolve_symbol(name)
    if name in _SYMBOL_MODULES:
        import importlib

        module = importlib.import_module(_SYMBOL_MODULES[name])
        # Cache in module globals for faster subsequent access
        globals()[name] = module
        return module
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "ask",
    "check",
    "feedback",
    "flow",
    "handoff",
    "inspect",
    "plan",
    "pr",
    "review",
    "run",
    "snapshot",
    "suggest_next_step",
    "render_blocked_items",
    "render_completed_flows",
    "render_epic_items",
    "render_human_collab_flows",
    "render_issue_progress",
    "render_missing_state_items",
    "render_pr_ref_items",
    "render_remote_items",
    "render_rfc_items",
    "render_supervisor_issues",
]
