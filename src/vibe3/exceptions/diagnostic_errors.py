"""Missing resource error with diagnostic context.

Note: DiagnosticContext and MissingResourceError are defined in
__init__.py to avoid circular imports. This module re-exports them
for backward compatibility.
"""

from __future__ import annotations

from vibe3.exceptions import DiagnosticContext, MissingResourceError

__all__ = ["DiagnosticContext", "MissingResourceError"]
