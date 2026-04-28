"""FailedGate: global freeze signal based on persistent error tracking.

No longer checks GitHub labels. All state is persisted to SQLite:
- error_log table: records all errors
- failed_gate_state table: tracks gate activation state
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime

from loguru import logger

from vibe3.clients import SQLiteClient


@dataclass(frozen=True)
class GateResult:
    """Result of a failed gate check."""

    blocked: bool
    reason: str | None = None
    blocked_ticks: int = 0

    @classmethod
    def open_gate(cls) -> GateResult:
        """Create a non-blocking gate result."""
        return cls(blocked=False)


@dataclass
class GateStatus:
    """Full status of FailedGate for display."""

    is_active: bool
    reason: str | None
    triggered_at: str | None
    triggered_by_error_code: str | None
    cleared_at: str | None
    cleared_by: str | None
    cleared_reason: str | None
    blocked_ticks: int


class FailedGate:
    """Orchestra failed state gate.

    State machine:
    - OPEN: normal operation, check error thresholds each tick
    - ACTIVE: blocked, increment blocked_ticks, no auto-clear

    Trigger rules:
    - E_MODEL_* → immediate trigger
    - E_API_* (2+ in 3 ticks) → trigger

    Persistence:
    - State saved to failed_gate_state table
    - Survives process restarts
    - Manual clear via vibe3 serve resume
    """

    def __init__(self, store: SQLiteClient | None = None) -> None:
        """Initialize FailedGate with SQLite persistence.

        Args:
            store: SQLiteClient for database access
        """
        self.store = store or SQLiteClient()
        self.db_path = self.store.db_path

        # Ensure gate state row exists
        self._init_gate_state()

    def _init_gate_state(self) -> None:
        """Initialize failed_gate_state table if empty."""
        with sqlite3.connect(self.db_path) as conn:
            # Check if row exists
            row = conn.execute(
                "SELECT COUNT(*) FROM failed_gate_state WHERE id = 1"
            ).fetchone()

            if row[0] == 0:
                # Insert default row (OPEN state)
                conn.execute("""
                    INSERT INTO failed_gate_state (id, is_active, blocked_ticks)
                    VALUES (1, 0, 0)
                    """)

    def check(self) -> GateResult:
        """Check if orchestra dispatch should be frozen.

        Reads from failed_gate_state table:
        - If ACTIVE: return blocked with reason and blocked_ticks
        - If OPEN: check error thresholds, maybe activate

        Returns:
            GateResult: blocked=True if gate is ACTIVE or should activate
        """
        log = logger.bind(domain="orchestra", action="failed_gate_check")
        log.debug("Checking failed gate")

        # Read current state from database
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute("""
                SELECT is_active, reason, blocked_ticks
                FROM failed_gate_state
                WHERE id = 1
                """).fetchone()

        if not row:
            log.warning("Failed gate state row missing, assuming OPEN")
            return GateResult.open_gate()

        is_active, reason, blocked_ticks = row

        # If already ACTIVE, return blocked status
        if is_active:
            log.error(f"Failed gate is ACTIVE: {reason}")
            return GateResult(
                blocked=True,
                reason=reason or "Unknown reason",
                blocked_ticks=blocked_ticks,
            )

        # If OPEN, check error thresholds (maybe activate)
        threshold_result = self._check_error_threshold()

        if threshold_result.blocked:
            # Threshold reached, activate gate
            self.activate(threshold_result.reason or "Error threshold reached")
            return threshold_result

        # No threshold, gate remains OPEN
        log.debug("Failed gate is OPEN")
        return GateResult.open_gate()

    def _check_error_threshold(self) -> GateResult:
        """Check global error thresholds.

        Rules:
        - E_MODEL_* → immediate block
        - E_API_* (2+ in recent window) → block

        Returns:
            GateResult with blocked=True if threshold reached
        """
        from vibe3.exceptions.error_tracking import ErrorTrackingService

        log = logger.bind(domain="orchestra", action="error_threshold_check")
        log.debug("Checking error threshold")

        error_tracking = ErrorTrackingService.get_instance()

        # Check for model config errors (immediate block)
        if error_tracking.has_model_config_error():
            error_counts = error_tracking.get_error_counts()
            model_errors = [
                code for code in error_counts.keys() if code.startswith("E_MODEL_")
            ]
            log.error(f"Model config errors detected: {model_errors}")
            return GateResult(
                blocked=True,
                reason=f"Model configuration errors: {', '.join(model_errors)}",
            )

        # Check for frequent API errors (threshold: 2+ in window)
        api_error_count = error_tracking.get_api_error_count()

        if api_error_count >= 2:
            log.error(f"API error threshold reached: {api_error_count} errors")
            return GateResult(
                blocked=True,
                reason=f"API error threshold: {api_error_count} recent errors",
            )

        # No threshold reached
        log.debug(f"Error threshold check passed (API errors: {api_error_count})")
        return GateResult.open_gate()

    def activate(self, reason: str, error_code: str | None = None) -> None:
        """Activate failed gate.

        Args:
            reason: Reason for activation
            error_code: Optional error code that triggered activation
        """
        log = logger.bind(domain="orchestra", action="failed_gate_activate")
        log.error(f"Activating failed gate: {reason}")

        now = datetime.now(UTC).isoformat()

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                UPDATE failed_gate_state
                SET is_active = 1,
                    reason = ?,
                    triggered_at = ?,
                    triggered_by_error_code = ?,
                    blocked_ticks = 0
                WHERE id = 1
                """,
                (reason, now, error_code),
            )

    def clear(self, cleared_by: str, reason: str) -> None:
        """Clear failed gate (manual resume).

        Args:
            cleared_by: Who cleared (e.g., "admin:manual")
            reason: Reason for clearing
        """
        log = logger.bind(
            domain="orchestra",
            action="failed_gate_clear",
            cleared_by=cleared_by,
            reason=reason,
        )
        log.info("Clearing failed gate")

        now = datetime.now(UTC).isoformat()

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                UPDATE failed_gate_state
                SET is_active = 0,
                    cleared_at = ?,
                    cleared_by = ?,
                    cleared_reason = ?,
                    blocked_ticks = 0,
                    reason = NULL,
                    triggered_at = NULL,
                    triggered_by_error_code = NULL
                WHERE id = 1
                """,
                (now, cleared_by, reason),
            )

        # Also clear error log
        from vibe3.exceptions.error_tracking import ErrorTrackingService

        ErrorTrackingService.get_instance().clear(cleared_by, reason)

    def increment_blocked_ticks(self) -> None:
        """Increment blocked_ticks counter (called each tick when ACTIVE)."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE failed_gate_state
                SET blocked_ticks = blocked_ticks + 1
                WHERE id = 1 AND is_active = 1
                """)

    def get_status(self) -> GateStatus:
        """Get full gate status for display.

        Returns:
            GateStatus dataclass with all fields
        """
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute("""
                SELECT is_active, reason, triggered_at, triggered_by_error_code,
                       cleared_at, cleared_by, cleared_reason, blocked_ticks
                FROM failed_gate_state
                WHERE id = 1
                """).fetchone()

        if not row:
            return GateStatus(
                is_active=False,
                reason=None,
                triggered_at=None,
                triggered_by_error_code=None,
                cleared_at=None,
                cleared_by=None,
                cleared_reason=None,
                blocked_ticks=0,
            )

        return GateStatus(
            is_active=bool(row[0]),
            reason=row[1],
            triggered_at=row[2],
            triggered_by_error_code=row[3],
            cleared_at=row[4],
            cleared_by=row[5],
            cleared_reason=row[6],
            blocked_ticks=row[7],
        )
