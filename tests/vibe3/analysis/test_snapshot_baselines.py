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
