"""Tests for global runtime asset resolution."""

import subprocess
from pathlib import Path

from vibe3.clients.runtime_assets import resolve_runtime_asset, runtime_assets_root


def test_runtime_assets_root_uses_env_override(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("VIBE3_RUNTIME_ASSETS_ROOT", str(tmp_path))

    assert runtime_assets_root() == tmp_path


def test_resolve_supervisor_asset_prefers_global_distribution(
    monkeypatch, tmp_path: Path
) -> None:
    global_file = tmp_path / "supervisor/policies/plan.md"
    global_file.parent.mkdir(parents=True)
    global_file.write_text("global policy", encoding="utf-8")
    external_repo = tmp_path / "external"
    external_repo.mkdir()
    monkeypatch.setenv("VIBE3_RUNTIME_ASSETS_ROOT", str(tmp_path))
    monkeypatch.chdir(external_repo)

    resolved = resolve_runtime_asset("supervisor/policies/plan.md")

    assert resolved == global_file


def test_resolve_config_prompts_canonical_path(monkeypatch, tmp_path: Path) -> None:
    """Verify config/prompts resolves to ~/.vibe/config/prompts (not assets/prompts)."""
    global_file = tmp_path / "config/prompts/prompts.yaml"
    global_file.parent.mkdir(parents=True)
    global_file.write_text("prompts: {}", encoding="utf-8")
    external_repo = tmp_path / "external"
    external_repo.mkdir()
    monkeypatch.setenv("VIBE3_RUNTIME_ASSETS_ROOT", str(tmp_path))
    monkeypatch.chdir(external_repo)

    resolved = resolve_runtime_asset("config/prompts/prompts.yaml")

    assert resolved == global_file
    assert "assets/prompts" not in str(resolved)


def test_resolve_supervisor_policies_canonical_path(
    monkeypatch, tmp_path: Path
) -> None:
    """Verify supervisor/policies resolves to canonical path (not assets/policies)."""
    global_file = tmp_path / "supervisor/policies/run.md"
    global_file.parent.mkdir(parents=True)
    global_file.write_text("run policy", encoding="utf-8")
    external_repo = tmp_path / "external"
    external_repo.mkdir()
    monkeypatch.setenv("VIBE3_RUNTIME_ASSETS_ROOT", str(tmp_path))
    monkeypatch.chdir(external_repo)

    resolved = resolve_runtime_asset("supervisor/policies/run.md")

    assert resolved == global_file
    assert "assets/policies" not in str(resolved)


def test_resolve_vibe_project_asset_from_repo_root(monkeypatch, tmp_path: Path) -> None:
    """Verify .vibe/ paths resolve to git working tree root from repo root."""
    # Create a git repo with .vibe/policies
    vibe_file = tmp_path / ".vibe/policies/plan.md"
    vibe_file.parent.mkdir(parents=True)
    vibe_file.write_text("project policy", encoding="utf-8")

    # Initialize git repo with initial commit to ensure it's a valid repo
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    # Add initial commit to make the repo valid (skip hooks)
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "init", "--no-verify"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )

    # Change to repo root
    monkeypatch.chdir(tmp_path)

    # Clear the lru_cache before testing
    from vibe3.clients.runtime_assets import _git_toplevel

    _git_toplevel.cache_clear()

    resolved = resolve_runtime_asset(".vibe/policies/plan.md")

    assert resolved == vibe_file


def test_resolve_vibe_project_asset_from_subdirectory(
    monkeypatch, tmp_path: Path
) -> None:
    """Verify .vibe/ paths resolve correctly from subdirectory.

    This is the core bug scenario: orchestra serve from a subdirectory
    should still find .vibe/policies at the repo root.
    """
    # Create a git repo with .vibe/policies
    vibe_file = tmp_path / ".vibe/policies/plan.md"
    vibe_file.parent.mkdir(parents=True)
    vibe_file.write_text("project policy", encoding="utf-8")

    # Initialize git repo with initial commit
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "init", "--no-verify"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )

    # Create a subdirectory and change to it
    subdir = tmp_path / "src" / "vibe3"
    subdir.mkdir(parents=True)
    monkeypatch.chdir(subdir)

    # Clear the lru_cache before testing
    from vibe3.clients.runtime_assets import _git_toplevel

    _git_toplevel.cache_clear()

    resolved = resolve_runtime_asset(".vibe/policies/plan.md")

    # Should resolve to the same absolute path as from repo root
    assert resolved == vibe_file


def test_resolve_vibe_project_asset_not_in_repo(monkeypatch, tmp_path: Path) -> None:
    """Verify .vibe/ paths return relative path when not in a git repo."""
    # Create a non-git directory structure outside any git repo
    non_git_dir = tmp_path / "non-git"
    non_git_dir.mkdir()

    # Clear git environment variables to isolate from parent git repos
    monkeypatch.delenv("GIT_DIR", raising=False)
    monkeypatch.delenv("GIT_WORK_TREE", raising=False)
    monkeypatch.chdir(non_git_dir)

    # Clear the lru_cache before testing
    from vibe3.clients.runtime_assets import _git_toplevel

    _git_toplevel.cache_clear()

    resolved = resolve_runtime_asset(".vibe/policies/plan.md")

    # Should return the relative path as-is (caller handles gracefully)
    assert resolved == Path(".vibe/policies/plan.md")


def test_resolve_vibe_project_graceful_missing(monkeypatch, tmp_path: Path) -> None:
    """Verify .vibe/ paths resolve even if file doesn't exist.

    The caller (_read_file) will handle missing files gracefully by returning None.
    """
    # Create a git repo WITHOUT .vibe/policies with initial commit
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    # Create a dummy file and commit to make repo valid
    dummy = tmp_path / "README.md"
    dummy.write_text("test", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "init", "--no-verify"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )

    monkeypatch.chdir(tmp_path)

    # Clear the lru_cache before testing
    from vibe3.clients.runtime_assets import _git_toplevel

    _git_toplevel.cache_clear()

    resolved = resolve_runtime_asset(".vibe/policies/plan.md")

    # Should resolve to the expected path even if file doesn't exist
    expected = tmp_path / ".vibe/policies/plan.md"
    assert resolved == expected
    # But the file should not exist
    assert not resolved.exists()


def test_resolve_vibe_namespace_in_worktree(monkeypatch, tmp_path: Path) -> None:
    """Verify namespace="vibe" resolves to bundled project root when in worktree.

    This tests the core fix: @vibe/<path> should resolve using module path
    (bundled_project_root), not cwd, making it robust from subdirectories.
    """
    from vibe3.clients.runtime_assets import bundled_project_root

    # Get the actual bundled project root (this test runs within vibe3)
    bundled_root = bundled_project_root()

    # Change to a subdirectory within the project
    subdir = bundled_root / "src" / "vibe3"
    monkeypatch.chdir(subdir)

    # Resolve a vibe namespace asset
    resolved = resolve_runtime_asset("supervisor/policies/run.md", namespace="vibe")

    # Should resolve to bundled root
    expected = bundled_root / "supervisor/policies/run.md"
    assert resolved == expected


def test_resolve_vibe_namespace_from_subdirectory(monkeypatch, tmp_path: Path) -> None:
    """Verify namespace="vibe" works from a subdirectory (core bug fix).

    This is the key scenario: @vibe/<path> resolution should work from any
    subdirectory, not just from the project root. The fix delegates to
    bundled_project_root() which uses module __file__ resolution.
    """
    from vibe3.clients.runtime_assets import bundled_project_root

    bundled_root = bundled_project_root()

    # Create a deeply nested subdirectory
    deep_subdir = bundled_root / "src" / "vibe3" / "services" / "handoff"
    monkeypatch.chdir(deep_subdir)

    # Resolve a vibe namespace asset
    resolved = resolve_runtime_asset("supervisor/policies/run.md", namespace="vibe")

    # Should still resolve to bundled root
    expected = bundled_root / "supervisor/policies/run.md"
    assert resolved == expected


def test_resolve_vibe_namespace_external_project(monkeypatch, tmp_path: Path) -> None:
    """Verify namespace="vibe" falls back to global ~/.vibe from external project.

    When running from a non-vibe-center project, should fall back to the
    global distribution at ~/.vibe.
    """
    # Create an external project directory
    external_project = tmp_path / "external-project"
    external_project.mkdir()
    monkeypatch.chdir(external_project)

    # Set up a global distribution
    global_root = tmp_path / "global-vibe"
    global_file = global_root / "supervisor/policies/run.md"
    global_file.parent.mkdir(parents=True)
    global_file.write_text("global policy", encoding="utf-8")
    monkeypatch.setenv("VIBE3_RUNTIME_ASSETS_ROOT", str(global_root))

    # Resolve a vibe namespace asset
    resolved = resolve_runtime_asset("supervisor/policies/run.md", namespace="vibe")

    # Should fall back to global distribution
    assert resolved == global_file
