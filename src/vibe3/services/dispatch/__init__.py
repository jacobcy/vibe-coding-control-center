"""Dispatch services subpackage.

Provides dependency-resolution event handling and upstream closure gates.
"""

from vibe3.services.dispatch.dependency_closure_gate import DependencyClosureGate
from vibe3.services.dispatch.dependency_recheck_service import DependencyRecheckService

__all__ = [
    "DependencyRecheckService",
    "DependencyClosureGate",
]
