"""Tests for SQLiteClient with a fresh database (schema verification)."""

import sqlite3
from pathlib import Path

import pytest

from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.exceptions import GitError


def test_fresh_db_schema_no_deprecated_columns(tmp_path):
    """Verify that a fresh DB does not contain deprecated columns in flow_state."""
    db_path = tmp_path / "fresh.db"
    SQLiteClient(db_path=str(db_path))

    with sqlite3.connect(str(db_path)) as conn:
        cursor = conn.cursor()
        columns = {
            row[1] for row in cursor.execute("PRAGMA table_info(flow_state)").fetchall()
        }

    deprecated = {"task_issue_number", "pr_number", "pr_ready_for_review"}
    assert not (
        deprecated & columns
    ), f"Deprecated columns found: {deprecated & columns}"


def test_update_flow_state_success_on_fresh_db(tmp_path):
    """Verify that update_flow_state works on a fresh DB with valid fields."""
    db_path = tmp_path / "fresh.db"
    client = SQLiteClient(db_path=str(db_path))

    # Should NOT raise OperationalError
    client.update_flow_state(
        "task/test",
        flow_slug="test",
        flow_status="active",
    )

    state = client.get_flow_state("task/test")
    assert state is not None
    assert state["branch"] == "task/test"
    assert state["flow_slug"] == "test"


def test_get_flow_dependents_on_fresh_db(tmp_path):
    """Verify get_flow_dependents works on fresh DB without legacy columns."""
    db_path = tmp_path / "fresh.db"
    client = SQLiteClient(db_path=str(db_path))

    # Setup: feature/A (task #101)
    client.update_flow_state("feature/A", flow_slug="A", flow_status="active")
    client.add_issue_link("feature/A", 101, "task")

    # Setup: feature/B depends on task #101
    client.update_flow_state("feature/B", flow_slug="B", flow_status="active")
    client.add_issue_link("feature/B", 101, "dependency")

    # ACT
    dependents = client.get_flow_dependents("feature/A")

    # ASSERT
    assert dependents == ["feature/B"]


def test_default_db_path_uses_shared_git_common_dir(tmp_path, monkeypatch):
    """Default DB path should live under the shared git common dir."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    shared_git_dir = tmp_path / "shared" / ".git"
    shared_git_dir.mkdir(parents=True)
    monkeypatch.chdir(repo_root)
    monkeypatch.setattr(
        "vibe3.clients.sqlite_base.GitClient.get_git_common_dir",
        lambda self: str(shared_git_dir),
    )

    client = SQLiteClient()

    assert Path(client.db_path) == shared_git_dir / "vibe3" / "handoff.db"
    assert not (repo_root / "vibe3").exists()


def test_default_db_path_fails_fast_on_invalid_git_common_dir(tmp_path, monkeypatch):
    """Invalid git common dir should not create a local worktree DB."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)
    monkeypatch.setattr(
        "vibe3.clients.sqlite_base.GitClient.get_git_common_dir",
        lambda self: "",
    )

    with pytest.raises(GitError, match="returned empty path"):
        SQLiteClient()

    assert not (repo_root / "vibe3").exists()
