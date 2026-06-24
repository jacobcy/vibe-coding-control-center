"""Tests for snapshot baseline operations."""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest


def test_save_and_load_branch_baseline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test saving and loading branch baseline."""
    from vibe3.analysis import snapshot_service
    from vibe3.models.snapshot import StructureSnapshot

    # Mock paths
    baseline_dir = tmp_path / "vibe3" / "structure" / "baselines"

    monkeypatch.setattr(snapshot_service, "_get_baseline_dir", lambda: baseline_dir)

    # Create a minimal snapshot
    fake_git = MagicMock()
    fake_git.get_current_branch.return_value = "feature/issue-324"
    fake_git.get_current_commit.return_value = "abcdef1234567890"
    monkeypatch.setattr(snapshot_service, "GitClient", lambda: fake_git)

    # Mock the actual build - we just test saving/loading
    def fake_build() -> StructureSnapshot:
        return StructureSnapshot(
            snapshot_id="test-123",
            branch="feature/issue-324",
            commit="abcdef1234567890",
            commit_short="abcdef1",
            created_at="2026-04-20T10:00:00",
            root="src/vibe3",
            files=[],
            modules=[],
            dependencies=[],
            metrics={},
        )

    monkeypatch.setattr(snapshot_service, "build_snapshot", fake_build)

    # Save baseline
    result = snapshot_service.save_branch_baseline("feature/issue-324")
    assert result is not None
    assert result.exists()
    assert result.name == "baseline_feature-issue-324.json"

    # Load baseline back
    loaded = snapshot_service.load_branch_baseline("feature/issue-324")
    assert loaded is not None
    assert loaded.snapshot_id == "test-123"
    assert loaded.branch == "feature/issue-324"
    assert loaded.baseline_for == "feature/issue-324"


def test_load_branch_baseline_not_found(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test loading baseline for non-existent branch returns None."""
    from vibe3.analysis import snapshot_service

    baseline_dir = tmp_path / "vibe3" / "structure" / "baselines"
    baseline_dir.mkdir(parents=True)

    monkeypatch.setattr(snapshot_service, "_get_baseline_dir", lambda: baseline_dir)

    result = snapshot_service.load_branch_baseline("non-existent-branch")
    assert result is None


def test_load_branch_baseline_no_baseline_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test loading baseline when directory doesn't exist returns None."""
    from vibe3.analysis import snapshot_service

    baseline_dir = tmp_path / "vibe3" / "structure" / "baselines"
    # Don't create the directory

    monkeypatch.setattr(snapshot_service, "_get_baseline_dir", lambda: baseline_dir)

    result = snapshot_service.load_branch_baseline("main")
    assert result is None


def test_list_snapshots_excludes_baselines_by_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test list_snapshots excludes baselines by default."""
    from vibe3.analysis import snapshot_service

    snapshot_dir = tmp_path / "vibe3" / "structure" / "snapshots"
    snapshot_dir.mkdir(parents=True)

    baseline_dir = tmp_path / "vibe3" / "structure" / "baselines"
    baseline_dir.mkdir(parents=True)

    monkeypatch.setattr(snapshot_service, "_get_snapshot_dir", lambda: snapshot_dir)
    monkeypatch.setattr(snapshot_service, "_get_baseline_dir", lambda: baseline_dir)
    # Mock SQLiteClient to force filesystem fallback
    monkeypatch.setattr(
        snapshot_service,
        "SQLiteClient",
        lambda: (_ for _ in ()).throw(Exception("Mock DB failure")),
    )

    # Create a regular snapshot in snapshots directory
    regular = {
        "snapshot_id": "regular-1",
        "branch": "main",
        "commit": "abc123",
        "commit_short": "abc123",
        "created_at": "2026-04-20T10:00:00",
        "root": "src/vibe3",
        "baseline_for": None,
    }

    # Create a baseline in baselines directory
    baseline = {
        "snapshot_id": "baseline-main-1",
        "branch": "main",
        "commit": "def456",
        "commit_short": "def456",
        "created_at": "2026-04-20T11:00:00",
        "root": "src/vibe3",
        "baseline_for": "main",
    }

    (snapshot_dir / "regular-1.json").write_text(json.dumps(regular))
    (baseline_dir / "baseline-main.json").write_text(json.dumps(baseline))

    # Default - exclude baselines
    result = snapshot_service.list_snapshots()
    assert "regular-1" in result
    assert "baseline-main-1" not in result

    # With include_baselines=True
    result = snapshot_service.list_snapshots(include_baselines=True)
    assert "regular-1" in result
    assert "baseline-main-1" in result


def test_list_snapshots_from_db_with_baselines(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test list_snapshots DB path handles baseline filtering correctly."""
    from vibe3.analysis import snapshot_service

    # Mock SQLiteClient to return data with baseline_for
    mock_client = MagicMock()

    # When include_baselines=False, only return non-baseline snapshots
    mock_client.list_snapshots_from_registry.side_effect = lambda limit, include: (
        [
            {"snapshot_id": "regular-1", "created_at": "2026-06-15T10:00:00"},
            {"snapshot_id": "regular-2", "created_at": "2026-06-14T10:00:00"},
        ]
        if not include
        else [
            {"snapshot_id": "regular-1", "created_at": "2026-06-15T10:00:00"},
            {"snapshot_id": "regular-2", "created_at": "2026-06-14T10:00:00"},
            {"snapshot_id": "baseline-main-1", "created_at": "2026-06-13T10:00:00"},
        ]
    )

    monkeypatch.setattr(snapshot_service, "SQLiteClient", lambda: mock_client)

    # Test exclude baselines (default)
    result = snapshot_service.list_snapshots()
    assert result == ["regular-1", "regular-2"]
    mock_client.list_snapshots_from_registry.assert_called_once_with(50, False)

    # Test include baselines
    mock_client.reset_mock()
    result = snapshot_service.list_snapshots(include_baselines=True)
    assert result == ["regular-1", "regular-2", "baseline-main-1"]
    mock_client.list_snapshots_from_registry.assert_called_once_with(50, True)


def test_save_branch_baseline_creates_baseline_for_diff(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test save_branch_baseline creates baseline load_branch_baseline can find."""
    from vibe3.analysis import snapshot_service
    from vibe3.models.snapshot import StructureMetrics, StructureSnapshot

    baseline_dir = tmp_path / "vibe3" / "structure" / "baselines"
    baseline_dir.mkdir(parents=True)

    monkeypatch.setattr(snapshot_service, "_get_baseline_dir", lambda: baseline_dir)

    # Mock build_snapshot to return a minimal snapshot
    mock_snapshot = StructureSnapshot(
        snapshot_id="test-snapshot-1",
        branch="feature-test",
        commit="abc1234",
        commit_short="abc1234",
        created_at="2026-04-30T10:00:00",
        root="src/vibe3",
        files=[],
        modules=[],
        dependencies=[],
        metrics=StructureMetrics(
            total_files=10,
            total_loc=1000,
            total_functions=50,
            python_files=8,
        ),
    )
    monkeypatch.setattr(snapshot_service, "build_snapshot", lambda: mock_snapshot)

    # Save as baseline
    filepath = snapshot_service.save_branch_baseline("feature-test")
    assert filepath is not None
    assert filepath.exists()
    assert "baseline_feature-test.json" in str(filepath)

    # Load it back
    loaded = snapshot_service.load_branch_baseline("feature-test")
    assert loaded is not None
    assert loaded.snapshot_id == "test-snapshot-1"
    assert loaded.branch == "feature-test"
    assert loaded.baseline_for == "feature-test"


def test_save_branch_baseline_idempotent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test save_branch_baseline is idempotent with force=False."""
    from vibe3.analysis import snapshot_service
    from vibe3.models.snapshot import StructureMetrics, StructureSnapshot

    baseline_dir = tmp_path / "vibe3" / "structure" / "baselines"
    baseline_dir.mkdir(parents=True)

    monkeypatch.setattr(snapshot_service, "_get_baseline_dir", lambda: baseline_dir)

    # Mock build_snapshot to return different snapshots on each call
    call_count = 0

    def mock_build() -> StructureSnapshot:
        nonlocal call_count
        call_count += 1
        return StructureSnapshot(
            snapshot_id=f"test-snapshot-{call_count}",
            branch="feature-test",
            commit="abc1234",
            commit_short="abc1234",
            created_at=f"2026-04-30T10:00:0{call_count}",
            root="src/vibe3",
            files=[],
            modules=[],
            dependencies=[],
            metrics=StructureMetrics(
                total_files=10,
                total_loc=1000,
                total_functions=50,
                python_files=8,
            ),
        )

    monkeypatch.setattr(snapshot_service, "build_snapshot", mock_build)

    # First save with force=False -> baseline created
    filepath1 = snapshot_service.save_branch_baseline("feature-test", force=False)
    assert filepath1 is not None
    assert filepath1.exists()

    # Read the first snapshot
    data1 = json.loads(filepath1.read_text())
    assert data1["snapshot_id"] == "test-snapshot-1"

    # Second save with force=False -> returns same path, file unchanged
    filepath2 = snapshot_service.save_branch_baseline("feature-test", force=False)
    assert filepath2 is not None
    assert filepath2 == filepath1

    # Verify the file was not overwritten (still has first snapshot ID)
    data2 = json.loads(filepath2.read_text())
    assert data2["snapshot_id"] == "test-snapshot-1"

    # Save with force=True -> overwrites with new content
    filepath3 = snapshot_service.save_branch_baseline("feature-test", force=True)
    assert filepath3 is not None
    assert filepath3 == filepath1

    # Verify the file was overwritten (now has third snapshot ID)
    data3 = json.loads(filepath3.read_text())
    assert data3["snapshot_id"] == "test-snapshot-3"


def test_save_branch_baseline_forwards_repo_path_to_build_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When repo_path is passed, build_snapshot receives repo_path arg."""
    from vibe3.analysis import snapshot_baseline, snapshot_service

    baseline_dir = tmp_path / "vibe3" / "structure" / "baselines"
    baseline_dir.mkdir(parents=True)
    monkeypatch.setattr(snapshot_service, "_get_baseline_dir", lambda: baseline_dir)
    monkeypatch.setattr(snapshot_service, "_ensure_baseline_dir", lambda: None)

    captured_repo_path = []

    def fake_build_snapshot(root=None, repo_path=None):
        captured_repo_path.append(repo_path)
        from vibe3.models.snapshot import StructureSnapshot

        return StructureSnapshot(
            snapshot_id="test",
            branch="test-branch",
            commit="abc1234",
            commit_short="abc1234",
            created_at="2026-01-01T00:00:00",
            root="src/vibe3",
            files=[],
            modules=[],
            dependencies=[],
            metrics={},
        )

    # Monkeypatch build_snapshot at the module where it's defined
    monkeypatch.setattr(snapshot_service, "build_snapshot", fake_build_snapshot)

    worktree = tmp_path / "worktree"
    worktree.mkdir()

    snapshot_baseline.save_branch_baseline(
        "test-branch", force=True, repo_path=worktree
    )

    assert len(captured_repo_path) == 1
    assert captured_repo_path[0] == worktree


def test_backfill_baseline_registry_registers_files_with_baseline_for(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test backfill_baseline_registry registers files with baseline_for field."""
    from vibe3.analysis import snapshot_baseline, snapshot_service
    from vibe3.models.snapshot import StructureMetrics, StructureSnapshot

    baseline_dir = tmp_path / "vibe3" / "structure" / "baselines"
    baseline_dir.mkdir(parents=True)

    monkeypatch.setattr(snapshot_service, "_get_baseline_dir", lambda: baseline_dir)

    # Create three baseline files
    # Two with baseline_for field
    baseline1 = StructureSnapshot(
        snapshot_id="baseline-1",
        branch="main",
        commit="abc123",
        commit_short="abc123",
        created_at="2026-06-15T10:00:00",
        root="src/vibe3",
        files=[],
        modules=[],
        dependencies=[],
        metrics=StructureMetrics(
            total_files=10,
            total_loc=1000,
            total_functions=50,
            python_files=8,
        ),
        baseline_for="main",
    )
    (baseline_dir / "baseline_main.json").write_text(baseline1.model_dump_json())

    baseline2 = StructureSnapshot(
        snapshot_id="baseline-2",
        branch="feature/test",
        commit="def456",
        commit_short="def456",
        created_at="2026-06-16T10:00:00",
        root="src/vibe3",
        files=[],
        modules=[],
        dependencies=[],
        metrics=StructureMetrics(
            total_files=15,
            total_loc=1500,
            total_functions=75,
            python_files=12,
        ),
        baseline_for="feature/test",
    )
    (baseline_dir / "baseline_feature-test.json").write_text(
        baseline2.model_dump_json()
    )

    # One without baseline_for field (should be skipped)
    no_baseline = StructureSnapshot(
        snapshot_id="no-baseline",
        branch="other",
        commit="ghi789",
        commit_short="ghi789",
        created_at="2026-06-17T10:00:00",
        root="src/vibe3",
        files=[],
        modules=[],
        dependencies=[],
        metrics=StructureMetrics(
            total_files=5,
            total_loc=500,
            total_functions=25,
            python_files=4,
        ),
    )
    (baseline_dir / "regular_snapshot.json").write_text(no_baseline.model_dump_json())

    # Mock SQLiteClient - patch in snapshot_baseline module where it's used
    mock_client = MagicMock()
    monkeypatch.setattr(snapshot_baseline, "SQLiteClient", lambda: mock_client)

    # Run backfill
    result = snapshot_service.backfill_baseline_registry()

    # Verify counts
    assert result["registered"] == 2
    assert result["skipped"] == 1
    assert result["failed"] == 0

    # Verify upsert was called for the two baselines
    assert mock_client.upsert_snapshot_registry.call_count == 2


def test_backfill_baseline_registry_empty_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test backfill_baseline_registry with empty baseline directory."""
    from vibe3.analysis import snapshot_service

    baseline_dir = tmp_path / "vibe3" / "structure" / "baselines"
    baseline_dir.mkdir(parents=True)

    monkeypatch.setattr(snapshot_service, "_get_baseline_dir", lambda: baseline_dir)

    # Run backfill on empty directory
    result = snapshot_service.backfill_baseline_registry()

    # Verify all counts are 0
    assert result["registered"] == 0
    assert result["skipped"] == 0
    assert result["failed"] == 0


def test_backfill_baseline_registry_handles_db_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test backfill_baseline_registry handles DB write failures gracefully."""
    from vibe3.analysis import snapshot_baseline, snapshot_service
    from vibe3.models.snapshot import StructureMetrics, StructureSnapshot

    baseline_dir = tmp_path / "vibe3" / "structure" / "baselines"
    baseline_dir.mkdir(parents=True)

    monkeypatch.setattr(snapshot_service, "_get_baseline_dir", lambda: baseline_dir)

    # Create a baseline file
    baseline = StructureSnapshot(
        snapshot_id="baseline-fail",
        branch="main",
        commit="abc123",
        commit_short="abc123",
        created_at="2026-06-15T10:00:00",
        root="src/vibe3",
        files=[],
        modules=[],
        dependencies=[],
        metrics=StructureMetrics(
            total_files=10,
            total_loc=1000,
            total_functions=50,
            python_files=8,
        ),
        baseline_for="main",
    )
    (baseline_dir / "baseline_main.json").write_text(baseline.model_dump_json())

    # Mock SQLiteClient that raises on upsert - patch in snapshot_baseline module
    mock_client = MagicMock()
    mock_client.upsert_snapshot_registry.side_effect = Exception("DB write failed")
    monkeypatch.setattr(snapshot_baseline, "SQLiteClient", lambda: mock_client)

    # Run backfill - should not crash
    result = snapshot_service.backfill_baseline_registry()

    # Verify failed count is incremented
    assert result["registered"] == 0
    assert result["skipped"] == 0
    assert result["failed"] == 1
