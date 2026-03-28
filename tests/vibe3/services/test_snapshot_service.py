"""Tests for snapshot service baseline selection."""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from vibe3.services.snapshot_lookup import find_snapshot_by_branch
from vibe3.services.structure_service import FileStructure, FunctionInfo


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
    from vibe3.services import snapshot_lookup, snapshot_service

    monkeypatch.setattr(snapshot_service, "_get_snapshot_dir", lambda: snapshot_dir)
    monkeypatch.setattr(snapshot_lookup, "_get_snapshot_dir", lambda: snapshot_dir)

    result = find_snapshot_by_branch("main")

    assert result is not None
    assert result.branch == "main"
    assert result.snapshot_id == "2026-03-22T15-00-00_main_def5678"  # Most recent


def test_find_snapshot_by_branch_feature(
    snapshot_dir: Path, monkeypatch: pytest.MonkeyPatch
):
    """Test finding snapshot for feature branch."""
    from vibe3.services import snapshot_lookup, snapshot_service

    monkeypatch.setattr(snapshot_service, "_get_snapshot_dir", lambda: snapshot_dir)
    monkeypatch.setattr(snapshot_lookup, "_get_snapshot_dir", lambda: snapshot_dir)

    result = find_snapshot_by_branch("feature-xyz")

    assert result is not None
    assert result.branch == "feature-xyz"
    assert result.snapshot_id == "2026-03-23T12-00-00_feature-xyz_ghi9012"


def test_find_snapshot_by_branch_not_found(
    snapshot_dir: Path, monkeypatch: pytest.MonkeyPatch
):
    """Test finding snapshot for non-existent branch returns None."""
    from vibe3.services import snapshot_lookup, snapshot_service

    monkeypatch.setattr(snapshot_service, "_get_snapshot_dir", lambda: snapshot_dir)
    monkeypatch.setattr(snapshot_lookup, "_get_snapshot_dir", lambda: snapshot_dir)

    result = find_snapshot_by_branch("non-existent-branch")

    assert result is None


def test_find_snapshot_by_branch_origin_prefix(
    snapshot_dir: Path, monkeypatch: pytest.MonkeyPatch
):
    """Test finding snapshot with origin/ prefix normalization."""
    from vibe3.services import snapshot_lookup, snapshot_service

    monkeypatch.setattr(snapshot_service, "_get_snapshot_dir", lambda: snapshot_dir)
    monkeypatch.setattr(snapshot_lookup, "_get_snapshot_dir", lambda: snapshot_dir)

    # Should find "main" snapshot even when searching for "origin/main"
    result = find_snapshot_by_branch("origin/main")

    assert result is not None
    assert result.branch == "main"
    assert result.snapshot_id == "2026-03-22T15-00-00_main_def5678"


def test_find_snapshot_by_branch_empty_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Test finding snapshot in empty directory returns None."""
    from vibe3.services import snapshot_lookup, snapshot_service

    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    monkeypatch.setattr(snapshot_service, "_get_snapshot_dir", lambda: empty_dir)
    monkeypatch.setattr(snapshot_lookup, "_get_snapshot_dir", lambda: empty_dir)

    result = find_snapshot_by_branch("main")

    assert result is None


def test_find_snapshot_by_branch_nonexistent_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Test finding snapshot in non-existent directory returns None."""
    from vibe3.services import snapshot_lookup, snapshot_service

    nonexistent_dir = tmp_path / "nonexistent"
    monkeypatch.setattr(snapshot_service, "_get_snapshot_dir", lambda: nonexistent_dir)
    monkeypatch.setattr(snapshot_lookup, "_get_snapshot_dir", lambda: nonexistent_dir)

    result = find_snapshot_by_branch("main")

    assert result is None


def test_build_snapshot_uses_shared_python_collection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """build_snapshot should reuse shared Python file collection helper."""
    from vibe3.services import snapshot_service

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
