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
    assert snapshot.metrics.total_files == 2
    assert snapshot.files[0].imports == [f"imports:{str(root / 'a.py')}"]
    assert snapshot.files[1].imports == [f"imports:{str(root / 'b.py')}"]
    assert "imported_by" not in snapshot.files[0].model_dump()


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
