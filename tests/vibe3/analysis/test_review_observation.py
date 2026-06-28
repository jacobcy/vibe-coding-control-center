"""Real-Git tests for the evidence-only review observation."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import yaml

from vibe3.analysis.review_observation import build_review_observation
from vibe3.clients import GitClient


def _git(repo: Path, *args: str) -> str:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
        env=env,
    )
    return result.stdout.strip()


def _write(repo: Path, relative_path: str, content: str) -> None:
    path = repo / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")
    _write(repo, "base.txt", "base\n")
    _write(repo, "both.py", "value = 0\n")
    _write(repo, "unstaged.py", "value = 0\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "base")
    _git(repo, "switch", "-c", "feature")
    return repo


def _manifest(repo: Path, protected_path: str = "staged.py") -> Path:
    path = repo.parent / f"{repo.name}-review-kernel.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "architecture_packages": ["runtime", "orchestra"],
                "entries": [
                    {
                        "path": protected_path,
                        "responsibilities": ["fixture_state"],
                        "reason": "Fixture review path",
                        "review_floor": "focused",
                    }
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return path


def test_observation_splits_git_change_partitions(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    _write(repo, "committed.py", "committed = True\n")
    _git(repo, "add", "committed.py")
    _git(repo, "commit", "-m", "feature commit")

    _write(repo, "staged.py", "staged = True\n")
    _write(repo, "both.py", "value = 1\n")
    _git(repo, "add", "staged.py", "both.py")
    _write(repo, "both.py", "value = 2\n")
    _write(repo, "unstaged.py", "value = 1\n")
    _write(repo, "untracked.py", "untracked = True\n")
    manifest_path = _manifest(repo)

    result = build_review_observation(
        requested_base="main",
        resolved_base="main",
        git=GitClient(cwd=repo),
        manifest_path=manifest_path,
    )

    assert result.status == "ready"
    assert result.comparison is not None
    assert result.comparison.current_branch == "feature"
    assert result.comparison.head_sha == _git(repo, "rev-parse", "HEAD")
    assert result.comparison.merge_base_sha == _git(repo, "merge-base", "main", "HEAD")
    assert [item.path for item in result.changes.committed] == ["committed.py"]
    assert [item.path for item in result.changes.staged] == ["both.py", "staged.py"]
    assert [item.path for item in result.changes.unstaged] == [
        "both.py",
        "unstaged.py",
    ]
    assert [item.path for item in result.changes.untracked] == ["untracked.py"]
    assert result.changes.summary.unique_paths == 5
    assert result.kernel is not None
    assert result.kernel.impact == "small"
    assert result.kernel.review_hits[0].sources == ["staged"]
    assert result.review is not None
    assert result.review.minimum_depth == "focused"
    assert result.impact_analysis.status == "disabled"


def test_missing_manifest_keeps_git_facts_and_returns_partial(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    _write(repo, "committed.py", "committed = True\n")
    _git(repo, "add", "committed.py")
    _git(repo, "commit", "-m", "feature commit")

    result = build_review_observation(
        requested_base="main",
        resolved_base="main",
        git=GitClient(cwd=repo),
        manifest_path=repo / "config/v3/review_kernel.yaml",
    )

    assert result.status == "partial"
    assert [item.path for item in result.changes.committed] == ["committed.py"]
    assert result.kernel is not None
    assert result.kernel.status == "unavailable"
    assert result.kernel.impact == "none"
    assert result.diagnostics[0].code == "review_kernel_unavailable"


def test_unregistered_architecture_path_is_large_and_partial(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    _write(repo, "protected.py", "protected = True\n")
    manifest_path = _manifest(repo, "protected.py")
    _write(repo, "src/vibe3/runtime/new_kernel_file.py", "new = True\n")

    result = build_review_observation(
        requested_base="main",
        resolved_base="main",
        git=GitClient(cwd=repo),
        manifest_path=manifest_path,
    )

    assert result.status == "partial"
    assert result.kernel is not None
    assert result.kernel.impact == "large"
    assert result.kernel.status == "unavailable"
    assert result.kernel.diagnostics[0].code == "missing_manifest_entry"
    assert result.review is not None
    assert result.review.minimum_depth == "repeated"


def test_invalid_base_returns_error_without_empty_success(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    manifest_path = _manifest(repo, "base.txt")

    result = build_review_observation(
        requested_base="missing",
        resolved_base="missing",
        git=GitClient(cwd=repo),
        manifest_path=manifest_path,
    )

    assert result.status == "error"
    assert result.comparison is None
    assert result.diagnostics[0].code == "git_comparison_failed"


def test_committed_rename_and_binary_numstat_are_explicit(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    _write(repo, "rename_me.py", "value = 1\n")
    (repo / "binary.bin").write_bytes(b"\x00before")
    _git(repo, "add", "rename_me.py", "binary.bin")
    _git(repo, "commit", "-m", "add rename and binary fixtures")
    _git(repo, "branch", "-f", "main", "HEAD")

    _git(repo, "mv", "rename_me.py", "renamed.py")
    (repo / "binary.bin").write_bytes(b"\x00after")
    _git(repo, "add", "renamed.py", "binary.bin")
    _git(repo, "commit", "-m", "rename and update binary")
    manifest_path = _manifest(repo, "base.txt")

    result = build_review_observation(
        requested_base="main",
        resolved_base="main",
        git=GitClient(cwd=repo),
        manifest_path=manifest_path,
    )

    facts = {fact.path: fact for fact in result.changes.committed}
    assert facts["renamed.py"].status == "R"
    assert facts["renamed.py"].old_path == "rename_me.py"
    assert facts["binary.bin"].binary is True
    assert facts["binary.bin"].additions is None
    assert facts["binary.bin"].deletions is None
    assert result.changes.summary.committed.additions is None
    assert result.changes.summary.committed.deletions is None
