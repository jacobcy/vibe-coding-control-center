"""Tests for SQLiteQueueRepo CRUD operations."""

import sqlite3

from vibe3.clients.sqlite_client import SQLiteClient


def test_fresh_db_has_orchestra_queue_table(tmp_path):
    """Verify orchestra_queue table exists with correct columns."""
    db_path = tmp_path / "test.db"
    SQLiteClient(db_path=str(db_path))

    with sqlite3.connect(str(db_path)) as conn:
        cursor = conn.cursor()
        columns = {
            row[1]: row[2]
            for row in cursor.execute("PRAGMA table_info(orchestra_queue)").fetchall()
        }

    assert columns["issue_number"] == "INTEGER"
    assert columns["collected_state"] == "TEXT"
    assert columns["waiting_state"] == "TEXT"
    assert columns["updated_at"] == "TEXT"


def test_remove_entry(tmp_path):
    """Save then remove — load returns None."""
    db_path = tmp_path / "test.db"
    client = SQLiteClient(db_path=str(db_path))

    # Setup: insert entry using raw SQL
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute(
            "INSERT INTO orchestra_queue (issue_number, collected_state, updated_at) "
            "VALUES (?, ?, datetime('now'))",
            (789, "to_remove"),
        )

    client.remove_queue_entry(789)

    # Verify: check entry is gone using raw SQL
    with sqlite3.connect(str(db_path)) as conn:
        row = conn.execute(
            "SELECT * FROM orchestra_queue WHERE issue_number = ?",
            (789,),
        ).fetchone()
    assert row is None


def test_remove_missing_is_noop(tmp_path):
    """Remove non-existent entry does not raise."""
    db_path = tmp_path / "test.db"
    client = SQLiteClient(db_path=str(db_path))

    client.remove_queue_entry(999)


def test_load_all_returns_all_entries(tmp_path):
    """Save 3 entries, load_all returns all 3."""
    db_path = tmp_path / "test.db"
    client = SQLiteClient(db_path=str(db_path))

    # Setup: insert 3 entries using raw SQL
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute(
            "INSERT INTO orchestra_queue (issue_number, collected_state, updated_at) "
            "VALUES (?, ?, datetime('now'))",
            (101, "a"),
        )
        conn.execute(
            "INSERT INTO orchestra_queue (issue_number, collected_state, updated_at) "
            "VALUES (?, ?, datetime('now'))",
            (102, "b"),
        )
        conn.execute(
            "INSERT INTO orchestra_queue (issue_number, collected_state, updated_at) "
            "VALUES (?, ?, datetime('now'))",
            (103, "c"),
        )

    entries = client.load_all_queue_entries()
    assert len(entries) == 3
    assert {e["issue_number"] for e in entries} == {101, 102, 103}


def test_replace_all_entries(tmp_path):
    """Save 2 entries, replace with 3 — only 3 remain."""
    db_path = tmp_path / "test.db"
    client = SQLiteClient(db_path=str(db_path))

    # Setup: insert 2 old entries using raw SQL
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute(
            "INSERT INTO orchestra_queue (issue_number, collected_state, updated_at) "
            "VALUES (?, ?, datetime('now'))",
            (201, "old1"),
        )
        conn.execute(
            "INSERT INTO orchestra_queue (issue_number, collected_state, updated_at) "
            "VALUES (?, ?, datetime('now'))",
            (202, "old2"),
        )

    new_entries = [
        {"issue_number": 301, "collected_state": "new1"},
        {"issue_number": 302, "collected_state": "new2"},
        {"issue_number": 303, "collected_state": "new3"},
    ]
    client.replace_all_queue_entries(new_entries)

    entries = client.load_all_queue_entries()
    assert len(entries) == 3
    assert {e["issue_number"] for e in entries} == {301, 302, 303}

    # Verify old entries are gone using raw SQL
    with sqlite3.connect(str(db_path)) as conn:
        row_201 = conn.execute(
            "SELECT * FROM orchestra_queue WHERE issue_number = ?",
            (201,),
        ).fetchone()
        row_202 = conn.execute(
            "SELECT * FROM orchestra_queue WHERE issue_number = ?",
            (202,),
        ).fetchone()
    assert row_201 is None
    assert row_202 is None


def test_replace_all_handles_duplicate_issue_numbers(tmp_path):
    """Replace with duplicate issue_numbers — last value wins."""
    db_path = tmp_path / "test.db"
    client = SQLiteClient(db_path=str(db_path))

    entries = [
        {"issue_number": 601, "collected_state": "first"},
        {"issue_number": 601, "collected_state": "second"},
        {"issue_number": 602, "collected_state": "other"},
    ]
    client.replace_all_queue_entries(entries)

    all_entries = client.load_all_queue_entries()
    assert len(all_entries) == 2
    # Find entry 601 and verify it has the second value
    entry_601 = next((e for e in all_entries if e["issue_number"] == 601), None)
    assert entry_601 is not None
    assert entry_601["collected_state"] == "second"


def test_legacy_enqueued_at_migration(tmp_path):
    """Simulate a legacy DB with enqueued_at NOT NULL, run init_schema,
    then verify save_queue_entry succeeds and both columns are populated."""
    db_path = tmp_path / "legacy.db"

    # Step 1: Create a legacy-style orchestra_queue with enqueued_at NOT NULL
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS orchestra_queue ("
            "issue_number INTEGER PRIMARY KEY, "
            "collected_state TEXT NOT NULL, "
            "waiting_state TEXT, "
            "enqueued_at TEXT NOT NULL, "
            "retry_count INTEGER NOT NULL DEFAULT 0, "
            "updated_at TEXT NOT NULL)"
        )
        # Insert a legacy row that only has the old columns
        conn.execute(
            "INSERT INTO orchestra_queue "
            "(issue_number, collected_state, waiting_state, "
            "enqueued_at, retry_count, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (100, "blocked", "ready", "2026-05-16T10:00:00", 0, "2026-05-16T10:00:00"),
        )

    # Step 2: Run init_schema (triggers migration)
    SQLiteClient(db_path=str(db_path))

    # Step 3: Verify migration added last_attempted_at
    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(orchestra_queue)")
        columns = {row[1] for row in cursor.fetchall()}
        assert "last_attempted_at" in columns

    # Step 4: Verify legacy row has last_attempted_at migrated from enqueued_at
    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM orchestra_queue WHERE issue_number = ?",
            (100,),
        ).fetchone()
        legacy_entry = dict(row) if row else None
    assert legacy_entry["last_attempted_at"] == "2026-05-16T10:00:00"

    # Step 5: Verify new inserts succeed (NOT NULL constraint satisfied)
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO orchestra_queue "
            "(issue_number, collected_state, waiting_state, retry_count, "
            "last_attempted_at, enqueued_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, datetime('now'))",
            (200, "blocked", "review", 2, "2026-05-17T09:00:00", "2026-05-17T09:00:00"),
        )

    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM orchestra_queue WHERE issue_number = ?",
            (200,),
        ).fetchone()
        new_entry = dict(row) if row else None
    assert new_entry["issue_number"] == 200
    assert new_entry["retry_count"] == 2
    assert new_entry["last_attempted_at"] == "2026-05-17T09:00:00"
    assert new_entry["enqueued_at"] == "2026-05-17T09:00:00"  # dual-written


def test_replace_all_with_legacy_enqueued_at(tmp_path):
    """Verify replace_all_queue_entries works on a legacy DB with enqueued_at."""
    db_path = tmp_path / "legacy2.db"

    # Create legacy schema
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS orchestra_queue ("
            "issue_number INTEGER PRIMARY KEY, "
            "collected_state TEXT NOT NULL, "
            "waiting_state TEXT, "
            "enqueued_at TEXT NOT NULL, "
            "retry_count INTEGER NOT NULL DEFAULT 0, "
            "updated_at TEXT NOT NULL)"
        )

    # Run migration
    client = SQLiteClient(db_path=str(db_path))

    # Replace all entries
    entries = [
        {
            "issue_number": 300,
            "collected_state": "ready",
            "waiting_state": None,
            "retry_count": 1,
            "last_attempted_at": "2026-05-17T08:00:00",
        },
    ]
    client.replace_all_queue_entries(entries)

    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM orchestra_queue WHERE issue_number = ?",
            (300,),
        ).fetchone()
        loaded = dict(row) if row else None
    assert loaded["retry_count"] == 1
    assert loaded["last_attempted_at"] == "2026-05-17T08:00:00"
    assert loaded["enqueued_at"] == "2026-05-17T08:00:00"


def test_queue_entry_persists_across_connections(tmp_path):
    """Queue writes should be committed for other connections to observe."""
    db_path = tmp_path / "persist.db"
    client = SQLiteClient(db_path=str(db_path))

    client.replace_all_queue_entries(
        [{"issue_number": 777, "collected_state": "persisted", "retry_count": 0}]
    )

    with sqlite3.connect(str(db_path)) as conn:
        row = conn.execute(
            "SELECT collected_state FROM orchestra_queue WHERE issue_number = ?",
            (777,),
        ).fetchone()

    assert row is not None
    assert row[0] == "persisted"


def test_queue_operations_persist_across_connections(tmp_path):
    """Queue delete/replace should be committed for other connections to observe."""
    db_path = tmp_path / "persist_ops.db"
    client = SQLiteClient(db_path=str(db_path))

    # Setup: insert 2 entries using raw SQL
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute(
            "INSERT INTO orchestra_queue (issue_number, collected_state, updated_at) "
            "VALUES (?, ?, datetime('now'))",
            (1, "one"),
        )
        conn.execute(
            "INSERT INTO orchestra_queue (issue_number, collected_state, updated_at) "
            "VALUES (?, ?, datetime('now'))",
            (2, "two"),
        )

    client.remove_queue_entry(1)
    client.replace_all_queue_entries(
        [{"issue_number": 3, "collected_state": "three", "retry_count": 0}]
    )

    with sqlite3.connect(str(db_path)) as conn:
        rows = conn.execute(
            "SELECT issue_number, collected_state "
            "FROM orchestra_queue ORDER BY issue_number"
        ).fetchall()

    assert rows == [(3, "three")]
