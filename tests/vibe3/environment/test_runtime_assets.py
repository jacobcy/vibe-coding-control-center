"""Tests for global runtime asset resolution."""

from pathlib import Path

from vibe3.utils.runtime_assets import resolve_runtime_asset, runtime_assets_root


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
