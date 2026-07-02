"""Confirmed state transition persistence and loop budget queries."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from vibe3.clients import SQLiteClient

SINGLE_STEP_LIMIT = 3
TRANSITION_LIMIT_SOFT = 10
TRANSITION_LIMIT_HARD = 20


@dataclass(frozen=True)
class TransitionRecordResult:
    """Counts produced by persisting one real state transition."""

    total_count: int
    pair_count: int
    total_limit_reached: bool
    pair_limit_reached: bool


class TransitionRecorder:
    """Persist confirmed transitions without selecting business targets."""

    def __init__(self, store: SQLiteClient) -> None:
        self._store = store

    def would_exceed(self, branch: str, from_state: str, to_state: str) -> bool:
        """Return whether one more code-owned transition would exceed a limit."""
        flow = self._store.get_flow_state(branch) or {}
        total = int(flow.get("transition_count", 0) or 0)
        with sqlite3.connect(self._store.db_path) as conn:
            pair = self._store.count_specific_pair(
                conn,
                branch,
                from_state,
                to_state,
            )
        return total + 1 >= TRANSITION_LIMIT_HARD or pair >= SINGLE_STEP_LIMIT

    def record_confirmed(
        self,
        *,
        branch: str,
        from_state: str,
        to_state: str,
        actor: str,
        issue_number: int,
    ) -> TransitionRecordResult:
        """Atomically record one already-confirmed state transition."""
        total, pair, _event_id = self._store.record_confirmed_transition(
            branch=branch,
            from_state=from_state,
            to_state=to_state,
            actor=actor,
            detail=f"State changed: {from_state} -> {to_state}",
            refs={
                "before_state": from_state,
                "after_state": to_state,
                "issue": str(issue_number),
            },
        )
        return TransitionRecordResult(
            total_count=total,
            pair_count=pair,
            total_limit_reached=total >= TRANSITION_LIMIT_HARD,
            pair_limit_reached=pair > SINGLE_STEP_LIMIT,
        )
