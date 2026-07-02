"""Dispatch services subpackage.

Provides upstream closure advisory notifications.

The observer-only dependency re-evaluation listener is tracked separately
in #3292 (depends on #3289); it must not route through
BlockedStateService.reconcile_blocked.
"""

from vibe3.services.dispatch.dependency_closure_gate import DependencyClosureGate

__all__ = [
    "DependencyClosureGate",
]
