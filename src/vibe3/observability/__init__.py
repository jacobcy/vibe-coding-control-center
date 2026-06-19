"""Observability module for Vibe 3.0.

This module provides unified management of logging and tracing:
- logger.py: Structured logging configuration
- trace_method.py: Method-level tracing via @trace_method decorator
- audit.py: Audit logging (future use)
- orchestra_log.py: Orchestra event logging (filesystem-backed)

Design Principles:
- Agent-friendly structured logging with semantic context
- Full error stack trace capture for debugging
- Precise code location (file:line:function) in DEBUG mode
- Rich integration for console beautification
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vibe3.observability.audit import AuditEntry, AuditLogger
    from vibe3.observability.degraded_mode import (
        DegradedModeManager,
        DegradedModeReason,
        get_degraded_manager,
    )
    from vibe3.observability.logger import setup_logging
    from vibe3.observability.orchestra_log import (
        append_governance_event,
        append_orchestra_event,
        append_orchestra_run_separator,
        governance_dry_run_dir,
        governance_events_log_path,
        governance_log_dir,
        orchestra_events_log_path,
        orchestra_log_dir,
        write_prompt_provenance,
    )
    from vibe3.observability.trace_method import (
        set_trace_max_lines,
        set_trace_min_ms,
    )

# Lazy imports (using absolute module paths)
_LAZY_IMPORTS = {
    "AuditEntry": "vibe3.observability.audit",
    "AuditLogger": "vibe3.observability.audit",
    "DegradedModeManager": "vibe3.observability.degraded_mode",
    "DegradedModeReason": "vibe3.observability.degraded_mode",
    "get_degraded_manager": "vibe3.observability.degraded_mode",
    "setup_logging": "vibe3.observability.logger",
    "append_governance_event": "vibe3.observability.orchestra_log",
    "append_orchestra_event": "vibe3.observability.orchestra_log",
    "append_orchestra_run_separator": "vibe3.observability.orchestra_log",
    "governance_dry_run_dir": "vibe3.observability.orchestra_log",
    "governance_events_log_path": "vibe3.observability.orchestra_log",
    "governance_log_dir": "vibe3.observability.orchestra_log",
    "orchestra_events_log_path": "vibe3.observability.orchestra_log",
    "orchestra_log_dir": "vibe3.observability.orchestra_log",
    "write_prompt_provenance": "vibe3.observability.orchestra_log",
    "set_trace_max_lines": "vibe3.observability.trace_method",
    "set_trace_min_ms": "vibe3.observability.trace_method",
    "trace_method": "vibe3.observability.trace_method",
}


def __getattr__(name: str) -> object:
    """Lazy import for observability symbols to avoid circular dependencies."""
    if name in _LAZY_IMPORTS:
        import importlib

        module = importlib.import_module(_LAZY_IMPORTS[name])
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "AuditEntry",
    "AuditLogger",
    "DegradedModeManager",
    "DegradedModeReason",
    "append_governance_event",
    "append_orchestra_event",
    "append_orchestra_run_separator",
    "governance_dry_run_dir",
    "governance_events_log_path",
    "governance_log_dir",
    "get_degraded_manager",
    "orchestra_events_log_path",
    "orchestra_log_dir",
    "set_trace_max_lines",
    "set_trace_min_ms",
    "setup_logging",
    "write_prompt_provenance",
]
