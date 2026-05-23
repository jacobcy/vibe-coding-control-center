"""Business logic violations - may trigger block_flow.

These errors represent business-level conditions that prevent progress:
- No-op (agent made no state change)
- Dependency not satisfied
- State transition loop detected
- Required field missing

Key principle: Business violations may trigger BLOCK system.
They can be handled by block_flow() which writes blocked_reason and label.
"""

from __future__ import annotations

from vibe3.exceptions import VibeError


class BusinessViolation(VibeError):  # noqa: N818
    """Base class for business logic violations.

    These errors indicate business-level conditions that block progress.
    They are handled by BLOCK system and may trigger block_flow().
    """

    def __init__(self, message: str) -> None:
        super().__init__(message, recoverable=True)


class NoOpViolation(BusinessViolation):
    """Agent execution made no state progress.

    Triggered when:
    - Issue state label unchanged after agent run
    - Required ref missing for worker role
    """


class DependencyViolation(BusinessViolation):
    """Required dependency not satisfied.

    Triggered when:
    - Blocked by another issue
    - Required sub-issue not completed
    """


class TransitionLoopViolation(BusinessViolation):
    """State transition loop detected.

    Triggered when:
    - Same state transition repeated too many times
    - Cycle detected in state machine
    """


class RequiredRefViolation(BusinessViolation):
    """Required reference/field missing.

    Triggered when:
    - Required report_ref missing
    - Required spec_ref missing
    - Required handoff file missing
    """
