"""Check domain services subpackage.

Public API Contract:
- CheckService: Main check orchestration service
- CheckResult: Result type for check operations
- CheckCleanupService: Cleanup service for check resources
- CheckPRService: PR-specific check operations
- InitResult: Result type for initialization

All other symbols are internal to the check package and should be imported directly.
"""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from vibe3.services.check.cleanup import CheckCleanupService
    from vibe3.services.check.pr_service import CheckPRService
    from vibe3.services.check.remote import InitResult
    from vibe3.services.check.service import CheckResult, CheckService

__all__ = [
    "CheckService",
    "CheckResult",
    "CheckCleanupService",
    "CheckPRService",
    "InitResult",
]

_SYMBOL_MODULES = {
    "CheckService": "vibe3.services.check.service",
    "CheckResult": "vibe3.services.check.service",
    "CheckCleanupService": "vibe3.services.check.cleanup",
    "CheckPRService": "vibe3.services.check.pr_service",
    "InitResult": "vibe3.services.check.remote",
}


def __getattr__(name: str) -> Any:
    """Lazy import for Check services symbols to avoid circular dependencies.

    This allows external modules to use:
        from vibe3.services.check import CheckService, CheckPRService

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
