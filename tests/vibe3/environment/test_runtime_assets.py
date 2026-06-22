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

    # Initialize git repo
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

    # Initialize git repo
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
    # Create a non-git directory structure
    non_git_dir = tmp_path / "non-git"
    non_git_dir.mkdir()
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
    # Create a git repo WITHOUT .vibe/policies
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
