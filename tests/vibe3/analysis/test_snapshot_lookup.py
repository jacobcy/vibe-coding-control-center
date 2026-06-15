"""Tests for snapshot lookup by branch."""

import json
from pathlib import Path

import pytest

from vibe3.analysis.snapshot_service import find_snapshot_by_branch
from vibe3.clients.sqlite_client import SQLiteClient


@pytest.fixture
def snapshot_db(tmp_path: Path) -> SQLiteClient:
    """Create an isolated DB with snapshot registry entries."""
    db_path = str(tmp_path / "test_handoff.db")
    client = SQLiteClient(db_path=db_path)
    return client


def test_find_snapshot_by_branch_main(
    snapshot_dir: Path, monkeypatch: pytest.MonkeyPatch
):
    """Test finding the most recent snapshot for main branch."""
    from vibe3.analysis import snapshot_service

    monkeypatch.setattr(snapshot_service, "_get_snapshot_dir", lambda: snapshot_dir)

    result = find_snapshot_by_branch("main")

    assert result is not None
    assert result.branch == "main"
    assert result.snapshot_id == "2026-03-22T15-00-00_main_def5678"  # Most recent


def test_find_snapshot_by_branch_feature(
    snapshot_dir: Path, monkeypatch: pytest.MonkeyPatch
):
    """Test finding snapshot for feature branch."""
    from vibe3.analysis import snapshot_service

    monkeypatch.setattr(snapshot_service, "_get_snapshot_dir", lambda: snapshot_dir)

    result = find_snapshot_by_branch("feature-xyz")

    assert result is not None
    assert result.branch == "feature-xyz"
    assert result.snapshot_id == "2026-03-23T12-00-00_feature-xyz_ghi9012"


def test_find_snapshot_by_branch_not_found(
    snapshot_dir: Path, monkeypatch: pytest.MonkeyPatch
):
    """Test finding snapshot for non-existent branch returns None."""
    from vibe3.analysis import snapshot_service

    monkeypatch.setattr(snapshot_service, "_get_snapshot_dir", lambda: snapshot_dir)

    result = find_snapshot_by_branch("non-existent-branch")

    assert result is None


def test_find_snapshot_by_branch_origin_prefix(
    snapshot_dir: Path, monkeypatch: pytest.MonkeyPatch
):
    """Test finding snapshot with origin/ prefix normalization."""
    from vibe3.analysis import snapshot_service

    monkeypatch.setattr(snapshot_service, "_get_snapshot_dir", lambda: snapshot_dir)

    # Should find "main" snapshot even when searching for "origin/main"
    result = find_snapshot_by_branch("origin/main")

    assert result is not None
    assert result.branch == "main"
    assert result.snapshot_id == "2026-03-22T15-00-00_main_def5678"


def test_find_snapshot_by_branch_empty_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Test finding snapshot in empty directory returns None."""
    from vibe3.analysis import snapshot_service

    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    monkeypatch.setattr(snapshot_service, "_get_snapshot_dir", lambda: empty_dir)

    result = find_snapshot_by_branch("main")

    assert result is None


def test_find_snapshot_by_branch_nonexistent_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Test finding snapshot in non-existent directory returns None."""
    from vibe3.analysis import snapshot_service

    nonexistent_dir = tmp_path / "nonexistent"
    monkeypatch.setattr(snapshot_service, "_get_snapshot_dir", lambda: nonexistent_dir)

    result = find_snapshot_by_branch("main")

    assert result is None


def test_find_snapshot_by_branch_glob_filters_candidates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Test that glob pre-filter correctly narrows candidates by branch."""
    from vibe3.analysis import snapshot_service

    # Create snapshots with branch names that share substrings
    snapshot_dir = tmp_path / "vibe3" / "structure" / "snapshots"
    snapshot_dir.mkdir(parents=True)

    snapshots = [
        {
            "snapshot_id": "2026-03-20T10-00-00_main_abc1234",
            "branch": "main",
            "commit": "abc1234",
            "commit_short": "abc1234",
            "created_at": "2026-03-20T10:00:00",
            "root": "src/vibe3",
            "files": [],
            "modules": [],
            "dependencies": [],
            "metrics": {},
        },
        {
            "snapshot_id": "2026-03-21T11-00-00_feature-main_xyz9876",
            "branch": "feature-main",
            "commit": "xyz9876",
            "commit_short": "xyz9876",
            "created_at": "2026-03-21T11:00:00",
            "root": "src/vibe3",
            "files": [],
            "modules": [],
            "dependencies": [],
            "metrics": {},
        },
        {
            "snapshot_id": "2026-03-22T12-00-00_main_def5678",
            "branch": "main",
            "commit": "def5678",
            "commit_short": "def5678",
            "created_at": "2026-03-22T12:00:00",
            "root": "src/vibe3",
            "files": [],
            "modules": [],
            "dependencies": [],
            "metrics": {},
        },
    ]

    for snapshot in snapshots:
        filepath = snapshot_dir / f"{snapshot['snapshot_id']}.json"
        filepath.write_text(json.dumps(snapshot, indent=2))

    monkeypatch.setattr(snapshot_service, "_get_snapshot_dir", lambda: snapshot_dir)

    # Search for "main" should only return snapshots with branch "main"
    # not "feature-main" even though glob pattern "*_main_*.json" matches both
    result = find_snapshot_by_branch("main")

    assert result is not None
    assert result.branch == "main"
    assert result.snapshot_id == "2026-03-22T12-00-00_main_def5678"  # Most recent


def test_find_snapshot_by_branch_fallback_for_nonconforming_filename(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Fallback scan finds snapshots whose filenames don't embed `_{branch}_`."""
    from vibe3.analysis import snapshot_service

    snapshot_dir = tmp_path / "vibe3" / "structure" / "snapshots"
    snapshot_dir.mkdir(parents=True)
    snapshot = {
        "snapshot_id": "flow-1-main-abc1234-2026-03-19T09-00-00",
        "branch": "main",
        "commit": "abc1234",
        "commit_short": "abc1234",
        "created_at": "2026-03-19T09:00:00",
        "root": "src/vibe3",
        "files": [],
        "modules": [],
        "dependencies": [],
        "metrics": {},
    }
    (snapshot_dir / f"{snapshot['snapshot_id']}.json").write_text(json.dumps(snapshot))
    monkeypatch.setattr(snapshot_service, "_get_snapshot_dir", lambda: snapshot_dir)

    result = find_snapshot_by_branch("main")

    assert result is not None
    assert result.snapshot_id == "flow-1-main-abc1234-2026-03-19T09-00-00"


def test_find_snapshot_by_branch_db_backed(
    snapshot_dir: Path, snapshot_db: SQLiteClient, monkeypatch: pytest.MonkeyPatch
):
    """Test DB-backed lookup returns correct snapshot when DB has entry."""
    from vibe3.analysis import snapshot_service

    monkeypatch.setattr(snapshot_service, "_get_snapshot_dir", lambda: snapshot_dir)

    # Create a factory function that returns the test client
    def get_test_client():
        return snapshot_db

    monkeypatch.setattr(snapshot_service, "SQLiteClient", get_test_client)

    # Register a snapshot in DB that's different from the file-based ones
    snapshot_db.upsert_snapshot_registry(
        snapshot_id="2026-03-24T10-00-00_main_zzz9999",
        branch="main",
        commit_short="zzz9999",
        commit_hash="zzz9999",
        created_at="2026-03-24T10:00:00",
        file_path=str(snapshot_dir / "2026-03-24T10-00-00_main_zzz9999.json"),
    )

    # Create the actual file so load_snapshot can read it
    snapshot_data = {
        "snapshot_id": "2026-03-24T10-00-00_main_zzz9999",
        "branch": "main",
        "commit": "zzz9999",
        "commit_short": "zzz9999",
        "created_at": "2026-03-24T10:00:00",
        "root": "src/vibe3",
        "files": [],
        "modules": [],
        "dependencies": [],
        "metrics": {},
    }
    (snapshot_dir / "2026-03-24T10-00-00_main_zzz9999.json").write_text(
        json.dumps(snapshot_data)
    )

    result = find_snapshot_by_branch("main")

    # Should return the DB-registered snapshot (most recent)
    assert result is not None
    assert result.branch == "main"
    assert result.snapshot_id == "2026-03-24T10-00-00_main_zzz9999"


def test_find_snapshot_by_branch_fallback_when_db_empty(
    snapshot_dir: Path, snapshot_db: SQLiteClient, monkeypatch: pytest.MonkeyPatch
):
    """Fallback to filesystem works when DB has no entries."""
    from vibe3.analysis import snapshot_service

    monkeypatch.setattr(snapshot_service, "_get_snapshot_dir", lambda: snapshot_dir)

    def get_test_client():
        return snapshot_db

    monkeypatch.setattr(snapshot_service, "SQLiteClient", get_test_client)

    # No DB entries — should fall back to filesystem scan
    result = find_snapshot_by_branch("main")

    assert result is not None
    assert result.branch == "main"


def test_find_snapshot_by_branch_db_failure_fallback(
    snapshot_dir: Path, monkeypatch: pytest.MonkeyPatch
):
    """Filesystem fallback kicks in when DB query raises exception."""
    from vibe3.analysis import snapshot_service

    monkeypatch.setattr(snapshot_service, "_get_snapshot_dir", lambda: snapshot_dir)

    # Make SQLiteClient raise an exception
    class FailClient:
        def find_snapshots_by_branch(self, branch, limit=20):
            raise RuntimeError("DB unavailable")

        def upsert_snapshot_registry(self, **kwargs):
            pass

    def get_fail_client():
        return FailClient()

    monkeypatch.setattr(snapshot_service, "SQLiteClient", get_fail_client)

    # Should still work via filesystem fallback
    result = find_snapshot_by_branch("main")

    assert result is not None
    assert result.branch == "main"
