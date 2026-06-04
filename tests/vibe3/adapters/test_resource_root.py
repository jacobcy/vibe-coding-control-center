"""Tests for adapter resource root resolution."""

from pathlib import Path

import pytest

from vibe3.adapters.resource_root import (
    ResourceRootNotFoundError,
    resolve_resource_root,
)


def test_resolve_resource_root_falls_back_to_parent_with_required_marker(
    monkeypatch, tmp_path: Path
) -> None:
    """Mocked git roots without resources should fall back to a valid cwd parent."""
    repo_root = tmp_path / "repo"
    nested = repo_root / "src" / "vibe3"
    nested.mkdir(parents=True)
    (repo_root / "skills").mkdir()
    mocked_common_dir = tmp_path / "isolated" / ".git"
    mocked_common_dir.mkdir(parents=True)

    monkeypatch.chdir(nested)

    resolved = resolve_resource_root(
        git_common_dir=str(mocked_common_dir),
        required_marker="skills",
    )

    assert resolved == repo_root


def test_resolve_resource_root_raises_when_no_required_marker(
    monkeypatch, tmp_path: Path
) -> None:
    """Resource lookup must fail explicitly instead of returning an empty cwd."""
    cwd = tmp_path / "not-repo"
    cwd.mkdir()
    mocked_common_dir = tmp_path / "isolated" / ".git"
    mocked_common_dir.mkdir(parents=True)

    monkeypatch.chdir(cwd)

    with pytest.raises(ResourceRootNotFoundError):
        resolve_resource_root(
            git_common_dir=str(mocked_common_dir),
            required_marker="skills",
        )
