"""Tests for snapshot service baseline selection."""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from vibe3.analysis.snapshot_service import find_snapshot_by_branch
from vibe3.analysis.structure_service import FileStructure, FunctionInfo


@pytest.fixture
def snapshot_dir(tmp_path: Path) -> Path:
    """Create a temporary snapshot directory with test data."""
    snapshot_dir = tmp_path / "vibe3" / "structure" / "snapshots"
    snapshot_dir.mkdir(parents=True)

    # Create test snapshots for different branches
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
            "snapshot_id": "2026-03-22T15-00-00_main_def5678",
            "branch": "main",
            "commit": "def5678",
            "commit_short": "def5678",
            "created_at": "2026-03-22T15:00:00",
            "root": "src/vibe3",
            "files": [],
            "modules": [],
            "dependencies": [],
            "metrics": {},
        },
        {
            "snapshot_id": "2026-03-23T12-00-00_feature-xyz_ghi9012",
            "branch": "feature-xyz",
            "commit": "ghi9012",
            "commit_short": "ghi9012",
            "created_at": "2026-03-23T12:00:00",
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

    return snapshot_dir


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


def test_build_snapshot_uses_shared_python_collection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """build_snapshot should reuse shared Python file collection helper."""
    from vibe3.analysis import snapshot_service

    root = tmp_path / "src" / "vibe3"
    root.mkdir(parents=True)
    (root / "a.py").write_text("def a():\n    return 1\n")
    (root / "b.py").write_text("def b():\n    return 2\n")

    fake_git = MagicMock()
    fake_git.get_current_branch.return_value = "task/demo"
    fake_git.get_current_commit.return_value = "abcdef1234567890"
    monkeypatch.setattr(snapshot_service, "GitClient", lambda: fake_git)

    collected = [
        FileStructure(
            path=str(root / "a.py"),
            language="python",
            total_loc=2,
            functions=[FunctionInfo(name="a", line=1, loc=2)],
            function_count=1,
        ),
        FileStructure(
            path=str(root / "b.py"),
            language="python",
            total_loc=2,
            functions=[FunctionInfo(name="b", line=1, loc=2)],
            function_count=1,
        ),
    ]

    collect_calls: list[str] = []

    def fake_collect(root_arg: str) -> list[FileStructure]:
        collect_calls.append(root_arg)
        return collected

    class Node:
        def __init__(self, imports: list[str]) -> None:
            self.imports = imports

    monkeypatch.setattr(
        snapshot_service.structure_service,
        "collect_python_file_structures",
        fake_collect,
    )
    monkeypatch.setattr(
        snapshot_service.dag_service,
        "_extract_imports",
        lambda path: [f"imports:{path}"],
    )
    monkeypatch.setattr(
        snapshot_service.dag_service,
        "build_module_graph",
        lambda root_arg: {
            "vibe3.a": Node([]),
            "vibe3.b": Node([]),
        },
    )

    snapshot = snapshot_service.build_snapshot(root=str(root))

    assert collect_calls == [str(root)]
    assert snapshot.metrics.total_files == 2
    assert snapshot.files[0].imports == [f"imports:{str(root / 'a.py')}"]
    assert snapshot.files[1].imports == [f"imports:{str(root / 'b.py')}"]
    assert "imported_by" not in snapshot.files[0].model_dump()


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
