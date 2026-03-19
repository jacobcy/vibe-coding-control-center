"""Observability module for Vibe 3.0.

This module provides unified management of logging, tracing, and auditing:
- logger.py: Structured logging configuration
- trace.py: Runtime call chain tracing (--trace support)
- audit.py: Audit logging (future use)

Design Principles:
- Agent-friendly structured logging with semantic context
- Full error stack trace capture for debugging
- Precise code location (file:line:function) in DEBUG mode
- Rich integration for console beautification
"""

from .logger import setup_logging
from .trace import Tracer, trace_context

__all__ = [
    "setup_logging",
    "Tracer",
    "trace_context",
]
