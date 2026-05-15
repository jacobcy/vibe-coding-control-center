"""Tests for SQLiteQueueRepo CRUD operations."""

import sqlite3
import time

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


def test_save_and_load_single_entry(tmp_path):
    """Save one entry, load it back — fields match."""
    db_path = tmp_path / "test.db"
    client = SQLiteClient(db_path=str(db_path))

    client.save_queue_entry(
        issue_number=123,
        collected_state="state_collected",
        waiting_state="state_waiting",
    )

    entry = client.load_queue_entry(123)
    assert entry["issue_number"] == 123
    assert entry["collected_state"] == "state_collected"
    assert entry["waiting_state"] == "state_waiting"
    assert entry["updated_at"] is not None


def test_save_overwrites_existing_entry(tmp_path):
    """Save twice — second write wins."""
    db_path = tmp_path / "test.db"
    client = SQLiteClient(db_path=str(db_path))

    client.save_queue_entry(456, collected_state="first")
    client.save_queue_entry(456, collected_state="second")

    entry = client.load_queue_entry(456)
    assert entry["collected_state"] == "second"


def test_load_missing_returns_none(tmp_path):
    """Load non-existent issue_number returns None."""
    db_path = tmp_path / "test.db"
    client = SQLiteClient(db_path=str(db_path))

    assert client.load_queue_entry(999) is None


def test_remove_entry(tmp_path):
    """Save then remove — load returns None."""
    db_path = tmp_path / "test.db"
    client = SQLiteClient(db_path=str(db_path))

    client.save_queue_entry(789, collected_state="to_remove")
    client.remove_queue_entry(789)

    assert client.load_queue_entry(789) is None


def test_remove_missing_is_noop(tmp_path):
    """Remove non-existent entry does not raise."""
    db_path = tmp_path / "test.db"
    client = SQLiteClient(db_path=str(db_path))

    client.remove_queue_entry(999)


def test_load_all_returns_all_entries(tmp_path):
    """Save 3 entries, load_all returns all 3."""
    db_path = tmp_path / "test.db"
    client = SQLiteClient(db_path=str(db_path))

    client.save_queue_entry(101, collected_state="a")
    client.save_queue_entry(102, collected_state="b")
    client.save_queue_entry(103, collected_state="c")

    entries = client.load_all_queue_entries()
    assert len(entries) == 3
    assert {e["issue_number"] for e in entries} == {101, 102, 103}


def test_replace_all_entries(tmp_path):
    """Save 2 entries, replace with 3 — only 3 remain."""
    db_path = tmp_path / "test.db"
    client = SQLiteClient(db_path=str(db_path))

    client.save_queue_entry(201, collected_state="old1")
    client.save_queue_entry(202, collected_state="old2")

    new_entries = [
        {"issue_number": 301, "collected_state": "new1"},
        {"issue_number": 302, "collected_state": "new2"},
        {"issue_number": 303, "collected_state": "new3"},
    ]
    client.replace_all_queue_entries(new_entries)

    entries = client.load_all_queue_entries()
    assert len(entries) == 3
    assert {e["issue_number"] for e in entries} == {301, 302, 303}
    assert client.load_queue_entry(201) is None
    assert client.load_queue_entry(202) is None


def test_updated_at_auto_set_on_save(tmp_path):
    """Save entry, updated_at is non-null."""
    db_path = tmp_path / "test.db"
    client = SQLiteClient(db_path=str(db_path))

    client.save_queue_entry(401, collected_state="test")
    assert client.load_queue_entry(401)["updated_at"] is not None


def test_updated_at_updates_on_second_save(tmp_path):
    """Save, wait, save again — updated_at changes."""
    db_path = tmp_path / "test.db"
    client = SQLiteClient(db_path=str(db_path))

    client.save_queue_entry(501, collected_state="first")
    first_updated = client.load_queue_entry(501)["updated_at"]

    time.sleep(0.01)

    client.save_queue_entry(501, collected_state="second")
    second_updated = client.load_queue_entry(501)["updated_at"]

    assert second_updated != first_updated


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
    entry_601 = client.load_queue_entry(601)
    assert entry_601 is not None
    assert entry_601["collected_state"] == "second"
