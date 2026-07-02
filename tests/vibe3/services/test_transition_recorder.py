"""Tests for confirmed transition accounting and loop budgets."""

import sqlite3

import pytest

from vibe3.clients import SQLiteClient
from vibe3.services.flow.transition_recorder import TransitionRecorder


@pytest.fixture
def store(tmp_path) -> SQLiteClient:
    client = SQLiteClient(db_path=str(tmp_path / "recorder.db"))
    client.update_flow_state(
        "task/issue-42",
        flow_status="active",
        transition_count=0,
    )
    return client


def test_record_confirmed_returns_total_and_pair_counts(store: SQLiteClient) -> None:
    result = TransitionRecorder(store).record_confirmed(
        branch="task/issue-42",
        from_state="state/review",
        to_state="state/merge-ready",
        actor="agent:reviewer",
        issue_number=42,
    )

    assert result.total_count == 1
    assert result.pair_count == 1
    assert result.total_limit_reached is False
    assert result.pair_limit_reached is False


def test_would_exceed_total_limit_before_code_owned_transition(
    store: SQLiteClient,
) -> None:
    store.update_flow_state("task/issue-42", transition_count=19)

    assert TransitionRecorder(store).would_exceed(
        "task/issue-42", "state/merge-ready", "state/handoff"
    )


def test_would_exceed_pair_limit_before_code_owned_transition(
    store: SQLiteClient,
) -> None:
    with sqlite3.connect(store.db_path) as conn:
        for _ in range(3):
            store.record_transition(
                conn,
                "task/issue-42",
                "state/merge-ready",
                "state/handoff",
                "agent:executor",
            )
        conn.commit()

    assert TransitionRecorder(store).would_exceed(
        "task/issue-42", "state/merge-ready", "state/handoff"
    )


def test_record_confirmed_reports_limit_crossing_for_observed_transition(
    store: SQLiteClient,
) -> None:
    store.update_flow_state("task/issue-42", transition_count=19)

    result = TransitionRecorder(store).record_confirmed(
        branch="task/issue-42",
        from_state="state/review",
        to_state="state/merge-ready",
        actor="agent:reviewer",
        issue_number=42,
    )

    assert result.total_count == 20
    assert result.total_limit_reached is True
