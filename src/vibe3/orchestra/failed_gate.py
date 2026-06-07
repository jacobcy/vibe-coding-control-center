"""Adapter shell for backward compatibility.

Re-exports FailedGate from domain layer for legacy imports.
All symbols are also available from their canonical locations:
- FailedGate: vibe3.domain.failed_gate.FailedGate
- GateResult: vibe3.domain.failed_gate.GateResult
- GateStatus: vibe3.domain.failed_gate.GateStatus
"""

from vibe3.domain import FailedGate, GateResult, GateStatus

__all__ = ["FailedGate", "GateResult", "GateStatus"]
