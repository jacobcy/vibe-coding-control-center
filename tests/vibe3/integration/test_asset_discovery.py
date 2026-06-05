"""Layer 1: Asset discovery smoke tests.

Tests that resolve_prompts_path(), resolve_runtime_asset(), and load_config()
can find assets from installed ~/.vibe without relying on source-tree fallback.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from vibe3.clients.runtime_assets import resolve_runtime_asset
from vibe3.config.loader import load_config
from vibe3.prompts.template_loader import resolve_prompts_path


def test_resolve_prompts_path_finds_global_prompts(installed_vibe_home: Path) -> None:
    """Test that resolve_prompts_path() finds prompts from installed ~/.vibe."""
    # Set VIBE3_RUNTIME_ASSETS_ROOT to temp home
    old_env = os.environ.get("VIBE3_RUNTIME_ASSETS_ROOT")
    os.environ["VIBE3_RUNTIME_ASSETS_ROOT"] = str(installed_vibe_home)

    try:
        prompts_path = resolve_prompts_path()

        # Assert path exists and contains expected keys
        assert prompts_path.exists(), f"Prompts path does not exist: {prompts_path}"

        # Check that it contains expected sections
        content = prompts_path.read_text(encoding="utf-8")
        # The prompts.yaml should contain run, plan, review keys
        # (not checking strict structure, just that it's a valid prompts file)
        assert (
            "run:" in content or "plan:" in content or "review:" in content
        ), f"Prompts file does not contain expected keys: {prompts_path}"
    finally:
        # Restore environment
        if old_env is not None:
            os.environ["VIBE3_RUNTIME_ASSETS_ROOT"] = old_env
        else:
            os.environ.pop("VIBE3_RUNTIME_ASSETS_ROOT", None)


def test_resolve_runtime_asset_finds_supervisor(installed_vibe_home: Path) -> None:
    """Test that resolve_runtime_asset() finds supervisor from installed ~/.vibe."""
    # Set VIBE3_RUNTIME_ASSETS_ROOT to temp home
    old_env = os.environ.get("VIBE3_RUNTIME_ASSETS_ROOT")
    os.environ["VIBE3_RUNTIME_ASSETS_ROOT"] = str(installed_vibe_home)

    try:
        supervisor_path = resolve_runtime_asset("supervisor/manager.md")

        # Assert path exists
        assert (
            supervisor_path.exists()
        ), f"Supervisor path does not exist: {supervisor_path}"
    finally:
        # Restore environment
        if old_env is not None:
            os.environ["VIBE3_RUNTIME_ASSETS_ROOT"] = old_env
        else:
            os.environ.pop("VIBE3_RUNTIME_ASSETS_ROOT", None)


def test_config_layering_loads_project_override(
    installed_vibe_home: Path,
    target_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that load_config() loads project override from target repo."""
    # Set VIBE3_RUNTIME_ASSETS_ROOT to temp home
    monkeypatch.setenv("VIBE3_RUNTIME_ASSETS_ROOT", str(installed_vibe_home))

    # Change CWD to target repo (load_config uses relative paths)
    monkeypatch.chdir(target_repo)

    # Create project config with an override that exists in VibeConfig schema
    vibe_dir = target_repo / ".vibe"
    vibe_dir.mkdir(exist_ok=True)
    settings_yaml = vibe_dir / "settings.yaml"
    settings_yaml.write_text(
        """flow:
  protected_branches:
    - main
    - master
    - test-protected-branch
""",
        encoding="utf-8",
    )

    # Load config
    config = load_config()

    # Assert the project override was loaded
    assert "test-protected-branch" in config.flow.protected_branches, (
        f"Project config override not loaded. "
        f"protected_branches: {config.flow.protected_branches}"
    )


def test_missing_prompts_detected(tmp_path: Path) -> None:
    """Test that missing prompts in global location fall back to bundled assets.

    When VIBE3_RUNTIME_ASSETS_ROOT points to an empty directory (no assets installed),
    resolve_prompts_path() should fall back to the bundled project root assets.
    This demonstrates that global assets are missing but the system still works
    via fallback.
    """
    # Create a temp dir WITHOUT config/prompts/
    empty_home = tmp_path / "empty_vibe"
    empty_home.mkdir()

    # Set VIBE3_RUNTIME_ASSETS_ROOT to empty dir
    old_env = os.environ.get("VIBE3_RUNTIME_ASSETS_ROOT")
    os.environ["VIBE3_RUNTIME_ASSETS_ROOT"] = str(empty_home)

    try:
        prompts_path = resolve_prompts_path()

        # The path should exist (via bundled fallback)
        assert prompts_path.exists(), (
            f"Expected prompts path to exist via bundled fallback, "
            f"but it doesn't: {prompts_path}"
        )

        # But it should NOT be from the empty global location
        assert not str(prompts_path).startswith(str(empty_home)), (
            f"Expected fallback to bundled assets, but got path from "
            f"global location: {prompts_path}"
        )

        # Record failure category (for documentation)
        # This demonstrates that global install is missing, but system
        # works via fallback
    finally:
        # Restore environment
        if old_env is not None:
            os.environ["VIBE3_RUNTIME_ASSETS_ROOT"] = old_env
        else:
            os.environ.pop("VIBE3_RUNTIME_ASSETS_ROOT", None)


def test_missing_supervisor_detected(tmp_path: Path) -> None:
    """Test that missing supervisor in global location fall back to bundled assets.

    When VIBE3_RUNTIME_ASSETS_ROOT points to an empty directory (no assets installed),
    resolve_runtime_asset() should fall back to the bundled project root assets.
    This demonstrates that global assets are missing but the system still works
    via fallback.
    """
    # Create a temp dir WITHOUT supervisor/
    empty_home = tmp_path / "empty_vibe"
    empty_home.mkdir()

    # Set VIBE3_RUNTIME_ASSETS_ROOT to empty dir
    old_env = os.environ.get("VIBE3_RUNTIME_ASSETS_ROOT")
    os.environ["VIBE3_RUNTIME_ASSETS_ROOT"] = str(empty_home)

    try:
        supervisor_path = resolve_runtime_asset("supervisor/manager.md")

        # The path should exist (via bundled fallback)
        assert supervisor_path.exists(), (
            f"Expected supervisor path to exist via bundled fallback, "
            f"but it doesn't: {supervisor_path}"
        )

        # But it should NOT be from the empty global location
        assert not str(supervisor_path).startswith(str(empty_home)), (
            f"Expected fallback to bundled assets, but got path from "
            f"global location: {supervisor_path}"
        )

        # Record failure category (for documentation)
        # This demonstrates that global install is missing, but system
        # works via fallback
    finally:
        # Restore environment
        if old_env is not None:
            os.environ["VIBE3_RUNTIME_ASSETS_ROOT"] = old_env
        else:
            os.environ.pop("VIBE3_RUNTIME_ASSETS_ROOT", None)
