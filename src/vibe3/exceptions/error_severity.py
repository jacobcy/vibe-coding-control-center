"""Error severity classification for Orchestra runtime."""

from enum import Enum
from typing import Literal

from pydantic import BaseModel


class ErrorSeverity(str, Enum):
    """Canonical error severity levels for Orchestra runtime.

    Severity answers: "Does this signal indicate system unavailability,
    unstable infrastructure, or only a diagnostic warning?"

    See: docs/standards/v3/error-severity-and-blocking-standard.md
    """

    CRITICAL = "CRITICAL"  # Configuration unusable, stop immediately
    ERROR = "ERROR"  # Infrastructure unstable, track by threshold
    WARNING = "WARNING"  # Diagnostic/observability signal, no gate activation

    def __lt__(self, other: object) -> bool:
        """Enable severity comparison based on numeric level."""
        if isinstance(other, ErrorSeverity):
            return self._numeric_level() < other._numeric_level()
        return NotImplemented

    def __le__(self, other: object) -> bool:
        """Enable severity comparison based on numeric level."""
        if isinstance(other, ErrorSeverity):
            return self._numeric_level() <= other._numeric_level()
        return NotImplemented

    def __gt__(self, other: object) -> bool:
        """Enable severity comparison based on numeric level."""
        if isinstance(other, ErrorSeverity):
            return self._numeric_level() > other._numeric_level()
        return NotImplemented

    def __ge__(self, other: object) -> bool:
        """Enable severity comparison based on numeric level."""
        if isinstance(other, ErrorSeverity):
            return self._numeric_level() >= other._numeric_level()
        return NotImplemented

    def _numeric_level(self) -> int:
        """Return numeric level for comparison (higher = more severe)."""
        levels = {
            ErrorSeverity.WARNING: 1,
            ErrorSeverity.ERROR: 2,
            ErrorSeverity.CRITICAL: 3,
        }
        return levels[self]


class ErrorHandlingContract(BaseModel):
    """Registry-backed handling metadata for each error code.

    This replaces prefix-based inference (e.g., "all E_EXEC_* count toward threshold")
    with explicit semantics defined in the standard.
    """

    code: str
    severity: ErrorSeverity
    counts_toward_threshold: bool
    record_in_error_log: bool
    write_timeline_event: bool
    issue_action: Literal["record_only"]
    gate_action: Literal["ignore", "threshold", "immediate"]
    description: str = ""
