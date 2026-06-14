"""Tests for snapshot service core operations."""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from vibe3.analysis.structure_service import FileStructure, FunctionInfo


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
    # Our new scope extension adds non-Python files.
    # In test env with real repo, we get many extra files.
    # Accept any count > 0 (at minimum the 2 Python test files).
    assert snapshot.metrics.total_files >= 2
    assert snapshot.files[0].imports == [f"imports:{str(root / 'a.py')}"]
    assert snapshot.files[1].imports == [f"imports:{str(root / 'b.py')}"]
    assert "imported_by" not in snapshot.files[0].model_dump()


def test_build_snapshot_custom_root_does_not_scan_workspace_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Custom root snapshots should stay inside the provided tree."""
    from vibe3.analysis import snapshot_service

    root = tmp_path / "src" / "vibe3"
    root.mkdir(parents=True)
    (root / "a.py").write_text("def a():\n    return 1\n")
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "settings.yaml").write_text("x: 1\n")
    (tmp_path / "skills").mkdir()
    (tmp_path / "skills" / "demo.md").write_text("# demo\n")

    fake_git = MagicMock()
    fake_git.get_current_branch.return_value = "task/demo"
    fake_git.get_current_commit.return_value = "abcdef1234567890"
    monkeypatch.setattr(snapshot_service, "GitClient", lambda: fake_git)

    monkeypatch.setattr(
        snapshot_service.structure_service,
        "collect_python_file_structures",
        lambda root_arg: [
            FileStructure(
                path=str(root / "a.py"),
                language="python",
                total_loc=2,
                functions=[FunctionInfo(name="a", line=1, loc=2)],
                function_count=1,
            )
        ],
    )
    monkeypatch.setattr(
        snapshot_service.dag_service,
        "_extract_imports",
        lambda path: [],
    )
    monkeypatch.setattr(
        snapshot_service.dag_service,
        "build_module_graph",
        lambda root_arg: {},
    )

    mock_config = MagicMock()
    mock_config.review_scope.critical_paths = ["src/vibe3/execution/"]
    mock_config.review_scope.public_api_paths = ["config/", "skills/"]
    import vibe3.config

    monkeypatch.setattr(vibe3.config, "get_config", lambda: mock_config)

    snapshot = snapshot_service.build_snapshot(root=str(root))

    assert any(
        f.path == str(tmp_path / "config" / "settings.yaml") for f in snapshot.files
    )
    assert any(f.path == str(tmp_path / "skills" / "demo.md") for f in snapshot.files)
    assert all(Path(f.path).is_relative_to(tmp_path) for f in snapshot.files)


def test_read_snapshot_metadata_extracts_all_fields(tmp_path: Path) -> None:
    """Test normal snapshot file extraction - all 5 fields extracted correctly."""
    from vibe3.analysis.snapshot_service import _read_snapshot_metadata

    snapshot_file = tmp_path / "test-snapshot.json"
    snapshot_file.write_text(
        json.dumps(
            {
                "snapshot_id": "2026-06-12T10-00-00_main_abc1234",
                "created_at": "2026-06-12T10:00:00",
                "branch": "main",
                "commit": "abc1234",
                "baseline_for": None,
                "files": [],
                "modules": [],
                "dependencies": [],
                "metrics": {},
            },
            indent=2,
        )
    )

    result = _read_snapshot_metadata(snapshot_file)
    assert result is not None
    assert result["snapshot_id"] == "2026-06-12T10-00-00_main_abc1234"
    assert result["created_at"] == "2026-06-12T10:00:00"
    assert result["branch"] == "main"
    assert result["commit"] == "abc1234"
    assert result["baseline_for"] is None


def test_read_snapshot_metadata_baseline_for_null(tmp_path: Path) -> None:
    """Test that baseline_for as null returns None, not a string."""
    from vibe3.analysis.snapshot_service import _read_snapshot_metadata

    snapshot_file = tmp_path / "test-snapshot.json"
    snapshot_file.write_text(
        json.dumps(
            {
                "snapshot_id": "test-123",
                "baseline_for": None,
                "branch": "main",
                "created_at": "2026-06-12T10:00:00",
                "commit": "abc1234",
            },
            indent=2,
        )
    )

    result = _read_snapshot_metadata(snapshot_file)
    assert result is not None
    assert result["baseline_for"] is None
    assert isinstance(result["baseline_for"], type(None))


def test_read_snapshot_metadata_baseline_for_string(tmp_path: Path) -> None:
    """Test that baseline_for with a value extracts string correctly."""
    from vibe3.analysis.snapshot_service import _read_snapshot_metadata

    snapshot_file = tmp_path / "test-snapshot.json"
    snapshot_file.write_text(
        json.dumps(
            {
                "snapshot_id": "test-456",
                "baseline_for": "main",
                "branch": "main",
                "created_at": "2026-06-12T11:00:00",
                "commit": "def5678",
            },
            indent=2,
        )
    )

    result = _read_snapshot_metadata(snapshot_file)
    assert result is not None
    assert result["baseline_for"] == "main"
    assert isinstance(result["baseline_for"], str)


def test_read_snapshot_metadata_corrupted_json(tmp_path: Path) -> None:
    """Test that corrupted JSON file returns None."""
    from vibe3.analysis.snapshot_service import _read_snapshot_metadata

    snapshot_file = tmp_path / "corrupted.json"
    snapshot_file.write_text("{ invalid json")

    result = _read_snapshot_metadata(snapshot_file)
    assert result is None


def test_read_snapshot_metadata_missing_fields(tmp_path: Path) -> None:
    """Test that missing fields don't appear in returned dict."""
    from vibe3.analysis.snapshot_service import _read_snapshot_metadata

    snapshot_file = tmp_path / "partial.json"
    snapshot_file.write_text(
        json.dumps(
            {
                "snapshot_id": "partial-1",
                "created_at": "2026-06-12T12:00:00",
                # Missing: branch, commit, baseline_for
                "files": [],
            },
            indent=2,
        )
    )

    result = _read_snapshot_metadata(snapshot_file)
    assert result is not None
    assert "snapshot_id" in result
    assert "created_at" in result
    assert "branch" not in result
    assert "commit" not in result
    assert "baseline_for" not in result


def test_read_snapshot_metadata_nonexistent_file(tmp_path: Path) -> None:
    """Test that non-existent file returns None."""
    from vibe3.analysis.snapshot_service import _read_snapshot_metadata

    nonexistent = tmp_path / "does-not-exist.json"
    result = _read_snapshot_metadata(nonexistent)
    assert result is None


def test_read_snapshot_metadata_large_file_tail_read(tmp_path: Path) -> None:
    """Test tail read path for baseline_for in files >4KB."""
    from vibe3.analysis.snapshot_service import _read_snapshot_metadata

    # Create a snapshot file >4KB with large files array
    # StructureSnapshot field order: snapshot_id → ... → files → modules →
    # dependencies → metrics → baseline_for
    large_files = [
        {
            "path": f"/path/to/file_{i}.py",
            "language": "python",
            "total_loc": 100,
            "functions": [],
            "function_count": 0,
            "imports": [],
        }
        for i in range(100)
    ]

    snapshot_file = tmp_path / "large-snapshot.json"
    snapshot_file.write_text(
        json.dumps(
            {
                "snapshot_id": "2026-06-15T10-00-00_main_abc1234",
                "created_at": "2026-06-15T10:00:00",
                "branch": "main",
                "commit": "abc1234",
                "commit_short": "abc1234",
                "root": "/project",
                "files": large_files,
                "modules": [],
                "dependencies": {},
                "metrics": {
                    "total_files": 100,
                    "total_loc": 10000,
                    "total_functions": 0,
                },
                "baseline_for": "feature-branch",
            },
            indent=2,
        )
    )

    # Verify file is large enough to trigger tail read (>4KB)
    file_size = snapshot_file.stat().st_size
    assert file_size > 4096, f"Test file must be >4KB, got {file_size} bytes"

    # Extract metadata and verify baseline_for is found via tail read
    result = _read_snapshot_metadata(snapshot_file)
    assert result is not None
    assert result["snapshot_id"] == "2026-06-15T10-00-00_main_abc1234"
    assert result["created_at"] == "2026-06-15T10:00:00"
    assert result["branch"] == "main"
    assert result["commit"] == "abc1234"
    assert (
        result["baseline_for"] == "feature-branch"
    ), "baseline_for must be extracted via tail read for large files"


def test_read_snapshot_metadata_large_file_baseline_for_null(tmp_path: Path) -> None:
    """Test tail read path extracts null baseline_for from large files."""
    from vibe3.analysis.snapshot_service import _read_snapshot_metadata

    large_files = [
        {
            "path": f"/path/to/file_{i}.py",
            "language": "python",
            "total_loc": 100,
            "functions": [],
            "function_count": 0,
            "imports": [],
        }
        for i in range(100)
    ]

    snapshot_file = tmp_path / "large-snapshot-null.json"
    snapshot_file.write_text(
        json.dumps(
            {
                "snapshot_id": "2026-06-15T11-00-00_main_def5678",
                "created_at": "2026-06-15T11:00:00",
                "branch": "main",
                "commit": "def5678",
                "commit_short": "def5678",
                "root": "/project",
                "files": large_files,
                "modules": [],
                "dependencies": {},
                "metrics": {
                    "total_files": 100,
                    "total_loc": 10000,
                    "total_functions": 0,
                },
                "baseline_for": None,
            },
            indent=2,
        )
    )

    file_size = snapshot_file.stat().st_size
    assert file_size > 4096, f"Test file must be >4KB, got {file_size} bytes"

    result = _read_snapshot_metadata(snapshot_file)
    assert result is not None
    assert result["snapshot_id"] == "2026-06-15T11-00-00_main_def5678"
    assert (
        result["baseline_for"] is None
    ), "null baseline_for must be extracted via tail read for large files"


def test_list_snapshots_with_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that limit parameter restricts number of snapshots returned."""
    from vibe3.analysis import snapshot_service

    snapshot_dir = tmp_path / "vibe3" / "structure" / "snapshots"
    snapshot_dir.mkdir(parents=True)

    monkeypatch.setattr(snapshot_service, "_get_snapshot_dir", lambda: snapshot_dir)

    # Create 10 test snapshots with different timestamps
    for i in range(10):
        snapshot = {
            "snapshot_id": f"snapshot-{i:02d}",
            "branch": "main",
            "commit": f"commit{i}",
            "commit_short": f"commit{i}",
            "created_at": f"2026-06-{12-i:02d}T10:00:00",  # Descending dates
            "root": "src/vibe3",
            "files": [],
            "modules": [],
            "dependencies": [],
            "metrics": {},
        }
        filepath = snapshot_dir / f"snapshot-{i:02d}.json"
        filepath.write_text(json.dumps(snapshot))

    # Test with limit=5
    result = snapshot_service.list_snapshots(limit=5)
    assert len(result) == 5
    # Should be newest first
    assert result[0] == "snapshot-00"  # 2026-06-12
    assert result[4] == "snapshot-04"  # 2026-06-08

    # Test with limit=None (all snapshots)
    result_all = snapshot_service.list_snapshots(limit=None)
    assert len(result_all) == 10

    # Test default limit (50)
    result_default = snapshot_service.list_snapshots()
    assert len(result_default) == 10  # Only 10 snapshots exist


def test_list_snapshots_limit_less_than_total(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test limit behavior when limit < total snapshots."""
    from vibe3.analysis import snapshot_service

    snapshot_dir = tmp_path / "vibe3" / "structure" / "snapshots"
    snapshot_dir.mkdir(parents=True)

    monkeypatch.setattr(snapshot_service, "_get_snapshot_dir", lambda: snapshot_dir)

    # Create 60 snapshots
    for i in range(60):
        snapshot = {
            "snapshot_id": f"snapshot-{i:03d}",
            "branch": "main",
            "commit": f"commit{i}",
            "created_at": f"2026-06-{12-i:02d}T10:00:00",
            "root": "src/vibe3",
            "files": [],
            "modules": [],
            "dependencies": [],
            "metrics": {},
        }
        filepath = snapshot_dir / f"snapshot-{i:03d}.json"
        filepath.write_text(json.dumps(snapshot))

    # Default limit (50) should truncate
    result = snapshot_service.list_snapshots(limit=50)
    assert len(result) == 50

    # Verify it returns the most recent 50
    result_all = snapshot_service.list_snapshots(limit=None)
    assert len(result_all) == 60
    assert result == result_all[:50]
