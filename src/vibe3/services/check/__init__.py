"""Check domain services subpackage."""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from vibe3.services.check.cleanup import CheckCleanupService
    from vibe3.services.check.lock import check_lock
    from vibe3.services.check.pr_service import CheckPRService
    from vibe3.services.check.remote import (
        CheckRemote,
        InitResult,
        is_empty_auto_scene,
        issue_state_from_payload,
        requires_handoff,
        resolve_task_issue_number,
    )
    from vibe3.services.check.service import CheckResult, CheckService

__all__ = [
    # Public API (exported via services/__init__.py)
    "CheckService",
    "CheckResult",
    "CheckCleanupService",
    "CheckPRService",
    "InitResult",
    # Internal API (used within check package)
    "check_lock",
    "CheckRemote",
    "issue_state_from_payload",
    "requires_handoff",
    "resolve_task_issue_number",
    "is_empty_auto_scene",
]

_SYMBOL_MODULES = {
    # Public API
    "CheckService": "vibe3.services.check.service",
    "CheckResult": "vibe3.services.check.service",
    "CheckCleanupService": "vibe3.services.check.cleanup",
    "CheckPRService": "vibe3.services.check.pr_service",
    "InitResult": "vibe3.services.check.remote",
    # Internal API
    "check_lock": "vibe3.services.check.lock",
    "CheckRemote": "vibe3.services.check.remote",
    "issue_state_from_payload": "vibe3.services.check.remote",
    "requires_handoff": "vibe3.services.check.remote",
    "resolve_task_issue_number": "vibe3.services.check.remote",
    "is_empty_auto_scene": "vibe3.services.check.remote",
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
