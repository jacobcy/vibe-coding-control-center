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

from .logger import setup_logging

__all__ = [
    "setup_logging",
]
