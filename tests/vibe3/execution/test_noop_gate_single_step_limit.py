"""Integration tests for single-step transition limit in no-op gate."""

import sqlite3
from datetime import datetime
from unittest.mock import MagicMock, patch

from vibe3.clients import init_schema
from vibe3.execution.noop_gate import apply_unified_noop_gate


def _make_github_issue_payload(state_label: str = "state/in-progress") -> dict:
    """Build a GitHub issue payload dict with given state label."""
    labels = [{"name": state_label}] if state_label else []
    return {"labels": labels, "state": "open"}


def test_single_step_limit_blocks_after_3_occurrences() -> None:
    """Block when the same transition pair has occurred 3+ times."""
    # Create in-memory database with full schema
    db_conn = sqlite3.connect(":memory:")
    init_schema(db_conn)

    # Insert 3 previous (state/handoff -> state/in-progress) transitions
    now = datetime.now().isoformat()
    db_conn.executemany(
        """
        INSERT INTO transition_history (branch, from_state, to_state, created_at, actor)
        VALUES (?, ?, ?, ?, ?)
        """,
        [
            (
                "task/issue-1034",
                "state/handoff",
                "state/in-progress",
                now,
                "executor:run1",
            ),
            (
                "task/issue-1034",
                "state/handoff",
                "state/in-progress",
                now,
                "executor:run2",
            ),
            (
                "task/issue-1034",
                "state/handoff",
                "state/in-progress",
                now,
                "executor:run3",
            ),
        ],
    )
    db_conn.commit()

    # Insert flow_state row with transition_count=0
    now_dt = datetime.now().isoformat()
    db_conn.execute(
        """
        INSERT INTO flow_state (branch, flow_slug, transition_count, updated_at)
        VALUES (?, ?, ?, ?)
        """,
        ("task/issue-1034", "task/issue-1034", 0, now_dt),
    )
    db_conn.commit()

    # Mock store with real db_path
    mock_store = MagicMock()
    mock_store.db_path = ":memory:"

    # Mock GitHub to return state/in-progress label
    mock_block_fn = MagicMock()

    with (
        patch(
            "vibe3.execution.noop_gate.get_role_block_function",
            return_value=mock_block_fn,
        ),
        patch("vibe3.clients.GitHubClient") as mock_gh,
        patch("sqlite3.connect", return_value=db_conn),
    ):
        mock_gh.return_value.view_issue.return_value = _make_github_issue_payload(
            "state/in-progress"
        )

        # Mock store methods that need to work with real DB
        def mock_count_specific_pair(
            conn: sqlite3.Connection, branch: str, from_state: str, to_state: str
        ) -> int:
            cursor = conn.cursor()
            row = cursor.execute(
                """
                SELECT COUNT(*)
                FROM transition_history
                WHERE branch = ? AND from_state = ? AND to_state = ?
                """,
                (branch, from_state, to_state),
            ).fetchone()
            return row[0] if row else 0

        mock_store.count_specific_pair = mock_count_specific_pair

        apply_unified_noop_gate(
            store=mock_store,
            issue_number=1034,
            branch="task/issue-1034",
            actor="executor:run3",
            role="executor",
            before_state_label="state/handoff",
        )

    # Assert block_fn called with reason containing single-step limit
    mock_block_fn.assert_called_once()
    call_args = mock_block_fn.call_args
    reason = call_args.kwargs.get("reason", "")
    assert "single-step limit exceeded" in reason
    assert "state/handoff -> state/in-progress" in reason
    assert "3 times" in reason

    db_conn.close()


def test_single_step_limit_allows_2_occurrences() -> None:
    """Allow transition when pair has occurred less than 3 times."""
    # Create in-memory database with full schema
    db_conn = sqlite3.connect(":memory:")
    init_schema(db_conn)

    # Insert 1 previous transition
    now = datetime.now().isoformat()
    db_conn.execute(
        """
        INSERT INTO transition_history (branch, from_state, to_state, created_at, actor)
        VALUES (?, ?, ?, ?, ?)
        """,
        ("task/issue-1034", "state/handoff", "state/in-progress", now, "executor:run1"),
    )
    db_conn.commit()

    # Insert flow_state row with transition_count=0
    now_dt = datetime.now().isoformat()
    db_conn.execute(
        """
        INSERT INTO flow_state (branch, flow_slug, transition_count, updated_at)
        VALUES (?, ?, ?, ?)
        """,
        ("task/issue-1034", "task/issue-1034", 0, now_dt),
    )
    db_conn.commit()

    # Mock store with real db_path
    mock_store = MagicMock()
    mock_store.db_path = ":memory:"

    # Mock GitHub to return state/in-progress label
    mock_block_fn = MagicMock()

    with (
        patch(
            "vibe3.execution.noop_gate.get_role_block_function",
            return_value=mock_block_fn,
        ),
        patch("vibe3.clients.GitHubClient") as mock_gh,
        patch("sqlite3.connect", return_value=db_conn),
    ):
        mock_gh.return_value.view_issue.return_value = _make_github_issue_payload(
            "state/in-progress"
        )

        # Mock store methods that need to work with real DB
        def mock_count_specific_pair(
            conn: sqlite3.Connection, branch: str, from_state: str, to_state: str
        ) -> int:
            cursor = conn.cursor()
            row = cursor.execute(
                """
                SELECT COUNT(*)
                FROM transition_history
                WHERE branch = ? AND from_state = ? AND to_state = ?
                """,
                (branch, from_state, to_state),
            ).fetchone()
            return row[0] if row else 0

        def mock_record_transition(
            conn: sqlite3.Connection,
            branch: str,
            from_state: str,
            to_state: str,
            actor: str,
            event_id: int | None = None,
        ) -> None:
            from datetime import datetime

            conn.execute(
                """
                INSERT INTO transition_history
                    (branch, from_state, to_state, created_at, actor, event_id)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    branch,
                    from_state,
                    to_state,
                    datetime.now().isoformat(),
                    actor,
                    event_id,
                ),
            )

        def mock_add_event(
            branch: str,
            event_type: str,
            actor: str,
            detail: str = "",
            refs: dict = None,
        ) -> None:
            # Simplified: just insert a row to satisfy the code
            cursor = db_conn.cursor()
            cursor.execute(
                """
                INSERT INTO flow_events
                    (branch, event_type, actor, detail, refs, created_at)
                VALUES (?, ?, ?, ?, ?, datetime('now'))
                """,
                (branch, event_type, actor, detail, str(refs) if refs else None),
            )

        mock_store.count_specific_pair = mock_count_specific_pair
        mock_store.record_transition = mock_record_transition
        mock_store.add_event = mock_add_event

        apply_unified_noop_gate(
            store=mock_store,
            issue_number=1034,
            branch="task/issue-1034",
            actor="executor:run2",
            role="executor",
            before_state_label="state/handoff",
        )

    # Assert block_fn NOT called
    mock_block_fn.assert_not_called()

    # Verify transition was recorded (pair_count should now be 2)
    cursor = db_conn.cursor()
    row = cursor.execute(
        """
        SELECT COUNT(*)
        FROM transition_history
        WHERE branch = ? AND from_state = ? AND to_state = ?
        """,
        ("task/issue-1034", "state/handoff", "state/in-progress"),
    ).fetchone()

    assert row[0] == 2, f"Expected 2 transitions, got {row[0]}"

    db_conn.close()
