"""Adapter shell for backward compatibility.

Re-exports FailedGate from domain layer for legacy imports.
All symbols are also available from their canonical locations:
- FailedGate: vibe3.domain.failed_gate.FailedGate
- GateResult: vibe3.orchestra.GateResult
- GateStatus: vibe3.orchestra.GateStatus
"""

import importlib

from vibe3.orchestra import GateResult, GateStatus


def __getattr__(name: str) -> object:
    """Lazy import for backward compatibility symbols."""
    if name == "FailedGate":
        return getattr(importlib.import_module("vibe3.domain"), "FailedGate")
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["FailedGate", "GateResult", "GateStatus"]  # noqa: F822
