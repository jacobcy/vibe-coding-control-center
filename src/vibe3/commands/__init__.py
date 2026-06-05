"""Commands package."""

from __future__ import annotations

# Lazy import mapping for command submodules
_SYMBOL_MODULES = {
    "ask": "vibe3.commands.ask",
    "check": "vibe3.commands.check",
    "flow": "vibe3.commands.flow",
    "handoff": "vibe3.commands.handoff",
    "inspect": "vibe3.commands.inspect",
    "plan": "vibe3.commands.plan",
    "pr": "vibe3.commands.pr",
    "review": "vibe3.commands.review",
    "run": "vibe3.commands.run",
    "snapshot": "vibe3.commands.snapshot",
}


def __getattr__(name: str) -> object:
    """Lazy import for command submodules."""
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
    "flow",
    "handoff",
    "inspect",
    "plan",
    "pr",
    "review",
    "run",
    "snapshot",
]
