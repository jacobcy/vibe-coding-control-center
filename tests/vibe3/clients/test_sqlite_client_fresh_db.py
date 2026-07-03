"""Tests for SQLiteClient with a fresh database (schema verification)."""

import sqlite3
import subprocess
from pathlib import Path

import pytest

from vibe3.clients.git_client import GitClient
from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.exceptions import GitError

_REAL_GET_GIT_COMMON_DIR = GitClient.get_git_common_dir


def test_fresh_db_schema_no_deprecated_columns(tmp_path):
    """Verify that a fresh DB does not contain deprecated columns in flow_state."""
    db_path = tmp_path / "fresh.db"
    SQLiteClient(db_path=str(db_path))

    with sqlite3.connect(str(db_path)) as conn:
        cursor = conn.cursor()
        columns = {
            row[1] for row in cursor.execute("PRAGMA table_info(flow_state)").fetchall()
        }

    deprecated = {
        "task_issue_number",
        "pr_number",
        "pr_ready_for_review",
        "latest_indicate_action",
    }
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


def test_default_db_path_reopens_closed_singleton_connection(tmp_path, monkeypatch):
    """Default-path client should recover if a previous caller closed the singleton."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    shared_git_dir = tmp_path / "shared" / ".git"
    shared_git_dir.mkdir(parents=True)
    monkeypatch.chdir(repo_root)
    monkeypatch.setattr(
        "vibe3.clients.sqlite_base.GitClient.get_git_common_dir",
        lambda self: str(shared_git_dir),
    )

    first = SQLiteClient()
    first._get_connection().close()

    second = SQLiteClient()
    second.update_flow_state("task/reopen", flow_slug="reopen", flow_status="active")

    state = second.get_flow_state("task/reopen")
    assert state is not None
    assert state["branch"] == "task/reopen"


def _init_non_bare_repo(path: Path) -> None:
    subprocess.run(
        ["git", "init", "-b", "main", str(path)],
        check=True,
        capture_output=True,
        text=True,
    )


class TestFromRepoPath:
    """Test SQLiteClient.from_repo_path classmethod."""

    def test_non_bare_repo_uses_dot_git_common_dir(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        non_bare_repo = tmp_path / "main"
        _init_non_bare_repo(non_bare_repo)
        monkeypatch.setattr(GitClient, "get_git_common_dir", _REAL_GET_GIT_COMMON_DIR)

        store = SQLiteClient.from_repo_path(non_bare_repo)

        assert Path(store.db_path) == (non_bare_repo / ".git" / "vibe3" / "handoff.db")

    def test_bare_repo_uses_repo_as_common_dir(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        non_bare_repo = tmp_path / "main"
        _init_non_bare_repo(non_bare_repo)
        bare_repo = tmp_path / "repo.git"
        subprocess.run(
            ["git", "clone", "--bare", str(non_bare_repo), str(bare_repo)],
            check=True,
            capture_output=True,
            text=True,
        )
        monkeypatch.setattr(GitClient, "get_git_common_dir", _REAL_GET_GIT_COMMON_DIR)

        store = SQLiteClient.from_repo_path(bare_repo)

        assert Path(store.db_path) == bare_repo / "vibe3" / "handoff.db"

    def test_returns_correct_subclass_type(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """from_repo_path should return SQLiteClient, not SQLiteClientBase."""
        repo = tmp_path / "main"
        _init_non_bare_repo(repo)
        monkeypatch.setattr(GitClient, "get_git_common_dir", _REAL_GET_GIT_COMMON_DIR)

        store = SQLiteClient.from_repo_path(repo)

        assert type(store).__name__ == "SQLiteClient"


def test_severity_prefix_map_matches_error_registry():
    """Verify inline severity map matches ERROR_REGISTRY.

    The migration backfill in sqlite_schema.py uses an inline severity map
    that must stay synchronized with ERROR_REGISTRY. This test catches drift.
    """
    from vibe3.exceptions.error_classification import ERROR_REGISTRY

    # Inline map from sqlite_schema.py (must be kept in sync)
    _severity_prefix_map: dict[str, str] = {
        "E_MODEL_": "CRITICAL",
        "E_API_": "ERROR",
        "E_EXEC_": "WARNING",
        "E_CAPACITY_": "WARNING",
        "E_DISPATCH_CODE": "ERROR",  # Permanent code bugs (must precede E_DISPATCH_)
        "E_DISPATCH_": "WARNING",  # Transient infrastructure
        "E_AUP_": "WARNING",  # AUP rejection
        "E_CONFIG_": "WARNING",
        "E_INVALID_": "ERROR",
        "E_ISSUE_": "ERROR",
        "E_TEST_": "WARNING",
    }

    # Verify each error code in registry matches prefix inference
    for error_code, contract in ERROR_REGISTRY.items():
        expected_severity = contract.severity.value

        # Infer severity from prefix
        actual_severity = "ERROR"  # Default fallback
        for prefix, sev in _severity_prefix_map.items():
            if error_code.startswith(prefix):
                actual_severity = sev
                break

        assert actual_severity == expected_severity, (
            f"{error_code}: inline map inferred {actual_severity}, "
            f"but ERROR_REGISTRY has {expected_severity}. "
            f"Update _severity_prefix_map in sqlite_schema.py"
        )
