"""Unit tests for SQLiteTransitionHistoryRepo methods."""

import sqlite3
from datetime import datetime

import pytest

from vibe3.clients.sqlite_schema import init_schema
from vibe3.clients.sqlite_transition_history_repo import (
    SQLiteTransitionHistoryRepo,
)


class TestTransitionHistoryRepo:
    """Test transition_history query methods."""

    @pytest.fixture
    def db_conn(self):
        """Create fresh database with schema."""
        conn = sqlite3.connect(":memory:")
        init_schema(conn)
        yield conn
        conn.close()

    @pytest.fixture
    def repo(self):
        """Create repo instance."""
        return SQLiteTransitionHistoryRepo()

    @pytest.fixture
    def populated_db(self, db_conn):
        """Populate database with test transitions."""
        cursor = db_conn.cursor()

        # Insert test data: branch "test-flow" with multiple transitions
        now = datetime.now().isoformat()
        test_transitions = [
            ("test-flow", "state/handoff", "state/in-progress", now, "actor1", None),
            ("test-flow", "state/handoff", "state/in-progress", now, "actor2", None),
            ("test-flow", "state/handoff", "state/in-progress", now, "actor3", None),
            ("test-flow", "state/in-progress", "state/handoff", now, "actor1", None),
            ("test-flow", "state/in-progress", "state/handoff", now, "actor2", None),
            ("test-flow", "state/ready", "state/claimed", now, "actor4", None),
        ]

        cursor.executemany(
            """
            INSERT INTO transition_history
                (branch, from_state, to_state, created_at, actor, event_id)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            test_transitions,
        )
        db_conn.commit()
        return db_conn

    def test_count_transition_pairs_basic(self, repo, populated_db):
        """Test basic pair counting."""
        result = repo.count_transition_pairs(populated_db, "test-flow")

        # Expected pairs:
        # (state/handoff, state/in-progress): 3
        # (state/in-progress, state/handoff): 2
        # (state/ready, state/claimed): 1
        assert result[("state/handoff", "state/in-progress")] == 3
        assert result[("state/in-progress", "state/handoff")] == 2
        assert result[("state/ready", "state/claimed")] == 1

    def test_count_transition_pairs_empty_branch(self, repo, db_conn):
        """Test counting for branch with no transitions."""
        result = repo.count_transition_pairs(db_conn, "empty-branch")
        assert result == {}

    def test_get_top_transition_pairs(self, repo, populated_db):
        """Test getting top pairs."""
        result = repo.get_top_transition_pairs(populated_db, "test-flow", limit=2)

        # Top 2 should be the pairs with 3 and 2 occurrences
        assert len(result) == 2
        assert result[0]["count"] == 3
        assert result[0]["from_state"] == "state/handoff"
        assert result[0]["to_state"] == "state/in-progress"

        assert result[1]["count"] == 2

    @pytest.mark.parametrize("limit", [3, 5, 10])
    def test_get_top_transition_pairs_valid_limits(self, repo, populated_db, limit):
        """Test with all valid Literal limit values."""
        result = repo.get_top_transition_pairs(populated_db, "test-flow", limit=limit)

        # Only 3 pairs exist in populated_db
        assert len(result) == 3

        # Verify ordering (descending by count)
        assert result[0]["count"] == 3
        assert result[1]["count"] == 2
        assert result[2]["count"] == 1

        # Verify descending order
        counts = [r["count"] for r in result]
        assert counts == sorted(counts, reverse=True)

    def test_count_specific_pair(self, repo, populated_db):
        """Test counting specific pair."""
        count = repo.count_specific_pair(
            populated_db,
            "test-flow",
            "state/handoff",
            "state/in-progress",
        )
        assert count == 3

        count_empty = repo.count_specific_pair(
            populated_db,
            "test-flow",
            "state/ready",
            "state/handoff",
        )
        assert count_empty == 0

    def test_record_transition(self, repo, db_conn):
        """Test recording new transition."""
        repo.record_transition(
            db_conn,
            "new-branch",
            "state/ready",
            "state/claimed",
            "test-actor",
            event_id=None,
        )

        # Verify it was inserted
        cursor = db_conn.cursor()
        row = cursor.execute("""
            SELECT COUNT(*) FROM transition_history
            WHERE branch = 'new-branch'
              AND from_state = 'state/ready'
              AND to_state = 'state/claimed'
            """).fetchone()

        assert row[0] == 1

    def test_record_transition_with_event_id(self, repo, db_conn):
        """Test recording transition with event_id reference."""
        # First insert a flow_event to get a valid event_id
        cursor = db_conn.cursor()
        cursor.execute(
            "INSERT INTO flow_events (branch, event_type, created_at, actor) "
            "VALUES (?, ?, datetime('now'), ?)",
            ("new-branch", "state_transitioned", "test-actor"),
        )
        db_conn.commit()

        # Get the inserted event_id
        event_id = cursor.execute(
            "SELECT id FROM flow_events WHERE branch = ?",
            ("new-branch",),
        ).fetchone()[0]

        repo.record_transition(
            db_conn,
            "new-branch",
            "state/ready",
            "state/claimed",
            "test-actor",
            event_id=event_id,
        )

        # Verify event_id was persisted
        cursor.execute(
            "SELECT event_id FROM transition_history "
            "WHERE branch = ? AND event_id IS NOT NULL",
            ("new-branch",),
        )
        assert cursor.fetchone()[0] == event_id

    def test_clear_transition_history_removes_all_records(self, repo, db_conn):
        """clear_transition_history should delete all records for a branch."""
        # Record some transitions
        repo.record_transition(
            db_conn, "test-branch", "state/claimed", "state/handoff", "actor1"
        )
        repo.record_transition(
            db_conn, "test-branch", "state/handoff", "state/claimed", "actor2"
        )
        repo.record_transition(
            db_conn, "other-branch", "state/ready", "state/claimed", "actor3"
        )

        # Clear test-branch
        repo.clear_transition_history(db_conn, "test-branch")

        # Verify test-branch records deleted
        cursor = db_conn.cursor()
        count_test = cursor.execute(
            "SELECT COUNT(*) FROM transition_history WHERE branch = ?",
            ("test-branch",),
        ).fetchone()[0]
        count_other = cursor.execute(
            "SELECT COUNT(*) FROM transition_history WHERE branch = ?",
            ("other-branch",),
        ).fetchone()[0]

        assert count_test == 0, "test-branch records should be deleted"
        assert count_other == 1, "other-branch records should remain"
