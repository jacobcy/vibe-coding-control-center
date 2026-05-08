"""Tests for repo_models_json_path with VIBE3_REPO_MODELS_ROOT override."""

import os
from pathlib import Path
from unittest.mock import patch


class TestRepoModelsJsonPath:
    """Tests for repo_models_json_path with VIBE3_REPO_MODELS_ROOT override."""

    def test_default_path_without_override(self) -> None:
        """Without override, should return default REPO_MODELS_JSON_PATH."""
        from vibe3.agents.backends.codeagent_config import (
            REPO_MODELS_JSON_PATH,
            repo_models_json_path,
        )

        with patch.dict(os.environ, {}, clear=True):
            result = repo_models_json_path()

        assert result == REPO_MODELS_JSON_PATH

    def test_override_path_with_env_var(self, tmp_path: Path) -> None:
        """With VIBE3_REPO_MODELS_ROOT, resolve to override/config/v3/models.json."""
        override_root = tmp_path / "custom_root"
        expected_path = override_root / "config" / "v3" / "models.json"

        with patch.dict(
            os.environ,
            {"VIBE3_REPO_MODELS_ROOT": str(override_root)},
            clear=True,
        ):
            from vibe3.agents.backends.codeagent_config import repo_models_json_path

            result = repo_models_json_path()

        assert result == expected_path

    def test_override_falls_back_to_legacy_models_path(self, tmp_path: Path) -> None:
        """Override root should support legacy config/models.json during migration."""
        override_root = tmp_path / "custom_root"
        legacy_path = override_root / "config" / "models.json"
        legacy_path.parent.mkdir(parents=True)
        legacy_path.write_text("{}", encoding="utf-8")

        with patch.dict(
            os.environ,
            {"VIBE3_REPO_MODELS_ROOT": str(override_root)},
            clear=True,
        ):
            from vibe3.agents.backends.codeagent_config import repo_models_json_path

            result = repo_models_json_path()

        assert result == legacy_path

    def test_override_supports_tilde_expansion(self) -> None:
        """VIBE3_REPO_MODELS_ROOT should support ~ expansion."""
        # Use a path with ~ that expands to home directory
        home_based = "~/custom-vibe-root"
        expected_base = Path(home_based).expanduser()
        expected_path = expected_base / "config" / "v3" / "models.json"

        with patch.dict(
            os.environ,
            {"VIBE3_REPO_MODELS_ROOT": home_based},
            clear=True,
        ):
            from vibe3.agents.backends.codeagent_config import repo_models_json_path

            result = repo_models_json_path()

        assert result == expected_path

    def test_override_resolves_to_absolute_path(self) -> None:
        """VIBE3_REPO_MODELS_ROOT should resolve to absolute path."""
        relative_path = "../custom-root"
        expected_base = Path(relative_path).expanduser().resolve()
        expected_path = expected_base / "config" / "v3" / "models.json"

        with patch.dict(
            os.environ,
            {"VIBE3_REPO_MODELS_ROOT": relative_path},
            clear=True,
        ):
            from vibe3.agents.backends.codeagent_config import repo_models_json_path

            result = repo_models_json_path()

        assert result == expected_path
        assert result.is_absolute()
