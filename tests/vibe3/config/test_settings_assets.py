"""Tests for settings integration with AssetResolver."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vibe3.config.settings import VibeConfig


def test_config_uses_asset_resolver_for_prompts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Config loader must use AssetResolver for prompt files."""
    # Setup: create global prompts
    global_dir = tmp_path / "global"
    global_prompts = global_dir / "prompts" / "prompts.yaml"
    global_prompts.parent.mkdir(parents=True)
    global_prompts.write_text("test_key: test_value\n")

    # Create a minimal config file at repo root
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    config_path = repo_root / "settings.yaml"
    config_path.write_text("flow:\n  protected_branches:\n    - main\n")

    monkeypatch.setenv("VIBE_ASSETS_DIR", str(global_dir))

    # Patch AssetResolver inside the function where it's imported
    mock_resolver_instance = MagicMock()
    mock_resolver_instance.resolve.return_value = global_prompts

    with patch(
        "vibe3.assets.resolver.AssetResolver", return_value=mock_resolver_instance
    ):
        # Trigger config loading which uses the resolver
        VibeConfig.from_yaml(config_path)

        # Verify resolver was called with correct parameters
        mock_resolver_instance.resolve.assert_called_once()
        call_args = mock_resolver_instance.resolve.call_args
        assert call_args[0][0] == "prompts/prompts.yaml"
        # repo_root should be determined from config_path
        assert "repo_root" in call_args[1]
        # repo_root should point to repo directory for settings.yaml at root
        assert call_args[1]["repo_root"] == repo_root
