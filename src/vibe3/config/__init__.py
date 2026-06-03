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
    "get_role_output_contract",
    "get_role_section",
    "GOVERNANCE_GATE_CONFIG",
    "resolve_effective_agent_options",
]

# Lazy import mapping for symbols to avoid circular dependencies
_SYMBOL_MODULES = {
    "ConventionResolver": "vibe3.config.convention_resolver",
    "get_role_output_contract": "vibe3.config.role_policy",
    "get_role_section": "vibe3.config.role_policy",
    "GOVERNANCE_GATE_CONFIG": "vibe3.config.role_gates",
    "resolve_effective_agent_options": "vibe3.config.agent_preset",
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
