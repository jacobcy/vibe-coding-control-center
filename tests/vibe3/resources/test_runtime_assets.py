"""Tests for global runtime asset resolution."""

from pathlib import Path

from vibe3.resources.runtime_assets import resolve_runtime_asset, runtime_assets_root


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
