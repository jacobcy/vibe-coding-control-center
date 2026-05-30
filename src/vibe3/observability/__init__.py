"""Observability module for Vibe 3.0.

This module provides unified management of logging and tracing:
- logger.py: Structured logging configuration
- trace_method.py: Method-level tracing via @trace_method decorator
- audit.py: Audit logging (future use)

Design Principles:
- Agent-friendly structured logging with semantic context
- Full error stack trace capture for debugging
- Precise code location (file:line:function) in DEBUG mode
- Rich integration for console beautification
"""

from .audit import AuditEntry, AuditLogger
from .degraded_mode import DegradedModeManager, DegradedModeReason, get_degraded_manager
from .logger import setup_logging
from .trace_method import set_trace_max_lines, set_trace_min_ms, trace_method

__all__ = [
    "AuditEntry",
    "AuditLogger",
    "DegradedModeManager",
    "DegradedModeReason",
    "get_degraded_manager",
    "set_trace_max_lines",
    "set_trace_min_ms",
    "setup_logging",
    "trace_method",
]
