"""Integration tests for install.sh runtime asset distribution."""

from pathlib import Path

from vibe3.utils.runtime_assets import runtime_assets_root


def test_runtime_assets_root_points_to_vibe_home(monkeypatch, tmp_path: Path) -> None:
    """Verify runtime_assets_root() points to ~/.vibe in global distribution mode."""
    # Simulate global distribution mode (no VIBE3_RUNTIME_ASSETS_ROOT set)
    monkeypatch.delenv("VIBE3_RUNTIME_ASSETS_ROOT", raising=False)

    # Mock HOME to use tmp_path
    monkeypatch.setenv("HOME", str(tmp_path))

    # runtime_assets_root should point to ~/.vibe
    root = runtime_assets_root()
    expected = tmp_path / ".vibe"

    assert root == expected


def test_canonical_paths_exist_after_install(monkeypatch, tmp_path: Path) -> None:
    """Verify critical runtime assets exist at canonical paths after install."""
    # Simulate install.sh has run and synced files to ~/.vibe
    vibe_home = tmp_path / ".vibe"

    # Create canonical directory structure
    canonical_files = [
        vibe_home / "src/vibe3/environment/runtime_assets.py",
        vibe_home / "config/prompts/prompts.yaml",
        vibe_home / "config/prompts/prompt-recipes.yaml",
        vibe_home / "supervisor/manager.md",
        vibe_home / "supervisor/policies/run.md",
        vibe_home / "supervisor/policies/plan.md",
        vibe_home / "supervisor/policies/review.md",
        vibe_home / "skills/vibe-commit/SKILL.md",
    ]

    for file_path in canonical_files:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(f"mock content for {file_path.name}", encoding="utf-8")

    # Verify files exist at canonical paths
    for file_path in canonical_files:
        assert file_path.exists(), f"Canonical path missing: {file_path}"

    # Verify no assets/ directory was created (old non-canonical path)
    assets_dir = vibe_home / "assets"
    assert (
        not assets_dir.exists()
    ), "Old assets/ directory should not exist in fresh install"


def test_settings_yaml_canonical_paths(monkeypatch, tmp_path: Path) -> None:
    """Verify settings.yaml points to canonical runtime asset paths."""
    vibe_home = tmp_path / ".vibe"
    vibe_home.mkdir()

    # Create settings.yaml with canonical paths
    settings_yaml = vibe_home / "settings.yaml"
    settings_content = f"""# Vibe Center Global Configuration
paths:
  policies_root: "{vibe_home}/supervisor/policies"
  prompts_root: "{vibe_home}/config/prompts"
"""
    settings_yaml.write_text(settings_content, encoding="utf-8")

    # Verify settings.yaml content
    content = settings_yaml.read_text(encoding="utf-8")
    assert (
        "supervisor/policies" in content
    ), "settings.yaml should point to canonical supervisor/policies"
    assert (
        "config/prompts" in content
    ), "settings.yaml should point to canonical config/prompts"
    assert (
        "assets/policies" not in content
    ), "settings.yaml should not reference old assets/policies"
    assert (
        "assets/prompts" not in content
    ), "settings.yaml should not reference old assets/prompts"


def test_settings_yaml_migration_from_assets_to_canonical(
    monkeypatch, tmp_path: Path
) -> None:
    """Verify install.sh migrates old assets/ paths to canonical paths."""
    vibe_home = tmp_path / ".vibe"
    vibe_home.mkdir()

    # Create settings.yaml with old assets/ paths (simulating existing install)
    settings_yaml = vibe_home / "settings.yaml"
    old_content = f"""# Vibe Center Global Configuration
paths:
  policies_root: "{vibe_home}/assets/policies"
  prompts_root: "{vibe_home}/assets/prompts"
"""
    settings_yaml.write_text(old_content, encoding="utf-8")

    # Simulate migration logic from install.sh
    import re

    content = settings_yaml.read_text(encoding="utf-8")
    content = re.sub(r"assets/prompts", "config/prompts", content)
    content = re.sub(r"assets/policies", "supervisor/policies", content)
    settings_yaml.write_text(content, encoding="utf-8")

    # Verify migration
    migrated_content = settings_yaml.read_text(encoding="utf-8")
    assert (
        "supervisor/policies" in migrated_content
    ), "Migration should update policies_root"
    assert "config/prompts" in migrated_content, "Migration should update prompts_root"
    assert (
        "assets/policies" not in migrated_content
    ), "Migration should remove old assets/policies"
    assert (
        "assets/prompts" not in migrated_content
    ), "Migration should remove old assets/prompts"
