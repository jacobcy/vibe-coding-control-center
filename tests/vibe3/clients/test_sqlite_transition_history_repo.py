"""Unit tests for SQLiteTransitionHistoryRepo methods."""

import sqlite3

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
        test_transitions = [
            ("test-flow", "state/handoff", "state/in-progress", "actor1", None),
            ("test-flow", "state/handoff", "state/in-progress", "actor2", None),
            ("test-flow", "state/handoff", "state/in-progress", "actor3", None),
            ("test-flow", "state/in-progress", "state/handoff", "actor1", None),
            ("test-flow", "state/in-progress", "state/handoff", "actor2", None),
            ("test-flow", "state/ready", "state/claimed", "actor4", None),
        ]

        cursor.executemany(
            """
            INSERT INTO transition_history
                (branch, from_state, to_state, actor, event_id)
            VALUES (?, ?, ?, ?, ?)
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
