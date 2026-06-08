"""Adapter shell for backward compatibility.

Re-exports FailedGate from domain layer for legacy imports.
All symbols are also available from their canonical locations:
- FailedGate: vibe3.domain.failed_gate.FailedGate
- GateResult: vibe3.domain.failed_gate.GateResult
- GateStatus: vibe3.domain.failed_gate.GateStatus
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vibe3.domain import FailedGate, GateResult, GateStatus


def __getattr__(name: str) -> object:
    if name == "FailedGate":
        from vibe3.domain import FailedGate

        return FailedGate
    if name == "GateResult":
        from vibe3.domain import GateResult

        return GateResult
    if name == "GateStatus":
        from vibe3.domain import GateStatus

        return GateStatus
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["FailedGate", "GateResult", "GateStatus"]
