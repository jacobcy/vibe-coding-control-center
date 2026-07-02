"""Dispatch services subpackage.

Provides upstream closure advisory notifications.

The observer-only dependency re-evaluation listener is tracked separately
in #3292 (depends on #3289); it must route through the auto eligibility
API (evaluate_auto_eligibility + apply_auto_resume) and must not clear a
human blocked_reason.
"""

from vibe3.services.dispatch.dependency_closure_gate import DependencyClosureGate

__all__ = [
    "DependencyClosureGate",
]
