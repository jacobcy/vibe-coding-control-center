"""Config package."""

from typing import Any

from vibe3.config.loader import get_config, load_config, reload_config
from vibe3.config.orchestra_settings import load_orchestra_config
from vibe3.config.settings import (
    CodeLimitsConfig,
    CodePathsConfig,
    MergeGateConfig,
    PRScoringConfig,
    QualityConfig,
    ReviewScopeConfig,
    SingleFileLocConfig,
    TestPathsConfig,
    TotalFileLocConfig,
    VibeConfig,
)

__all__ = [
    "get_config",
    "load_config",
    "load_orchestra_config",
    "reload_config",
    "VibeConfig",
    "CodeLimitsConfig",
    "SingleFileLocConfig",
    "TotalFileLocConfig",
    "CodePathsConfig",
    "TestPathsConfig",
    "ReviewScopeConfig",
    "QualityConfig",
    "PRScoringConfig",
    "MergeGateConfig",
    # Lazy imports
    "ConventionResolver",
]

# Lazy import mapping for symbols to avoid circular dependencies
_SYMBOL_MODULES = {
    "ConventionResolver": "vibe3.config.convention_resolver",
}


def __getattr__(name: str) -> Any:
    """Lazy import for config symbols to avoid circular dependencies.

    This allows external modules to use:
        from vibe3.config import ConventionResolver

    While avoiding circular imports at module load time.
    """
    if name in _SYMBOL_MODULES:
        import importlib

        module = importlib.import_module(_SYMBOL_MODULES[name])
        symbol = getattr(module, name)
        # Cache in module globals for faster subsequent access
        globals()[name] = symbol
        return symbol

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
