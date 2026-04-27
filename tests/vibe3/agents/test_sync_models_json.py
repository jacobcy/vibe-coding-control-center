"""Tests for sync_models_json behavior.

Tests syncing effective backend/model to ~/.codeagent/models.json.
"""

import json
from pathlib import Path
from unittest.mock import patch

from vibe3.agents.backends.codeagent_config import sync_models_json
from vibe3.models.review_runner import AgentOptions


class TestSyncModelsJson:
    """Tests for sync_models_json behavior."""

    def test_sync_writes_default_backend_and_model(self, tmp_path: Path) -> None:
        """sync_models_json should write default_backend and default_model."""
        models_path = tmp_path / ".codeagent" / "models.json"

        with patch(
            "vibe3.agents.backends.codeagent_config.MODELS_JSON_PATH",
            models_path,
        ):
            options = AgentOptions(backend="claude", model="claude-sonnet-4-6")
            sync_models_json(options)

        assert models_path.exists()
        data = json.loads(models_path.read_text())
        assert data["default_backend"] == "claude"
        assert data["default_model"] == "claude-sonnet-4-6"

    def test_sync_backend_only(self, tmp_path: Path) -> None:
        """sync_models_json should write default_backend only when model is None."""
        models_path = tmp_path / ".codeagent" / "models.json"

        with patch(
            "vibe3.agents.backends.codeagent_config.MODELS_JSON_PATH",
            models_path,
        ):
            options = AgentOptions(backend="gemini")
            sync_models_json(options)

        data = json.loads(models_path.read_text())
        assert data["default_backend"] == "gemini"
        assert "default_model" not in data

    def test_sync_skips_when_no_backend(self, tmp_path: Path) -> None:
        """sync_models_json should skip when neither preset nor default backend."""
        models_path = tmp_path / ".codeagent" / "models.json"
        repo_models = tmp_path / "config" / "models.json"
        repo_models.parent.mkdir(parents=True)
        repo_models.write_text(json.dumps({"agents": {}}))  # no default_backend

        import pytest

        from vibe3.exceptions import AgentPresetNotFoundError

        with (
            patch(
                "vibe3.agents.backends.codeagent_config.MODELS_JSON_PATH",
                models_path,
            ),
            patch(
                "vibe3.agents.backends.codeagent_config.REPO_MODELS_JSON_PATH",
                repo_models,
            ),
            pytest.raises(AgentPresetNotFoundError),
        ):
            options = AgentOptions(agent="some-preset")
            sync_models_json(options)

        # Should not create file (exception raised before write)
        assert not models_path.exists()

    def test_sync_preserves_existing_fields(self, tmp_path: Path) -> None:
        """sync_models_json should preserve existing fields in models.json."""
        models_path = tmp_path / ".codeagent" / "models.json"
        models_path.parent.mkdir(parents=True)
        models_path.write_text(
            json.dumps(
                {
                    "agents": {"custom-agent": {"backend": "openai"}},
                    "other_field": "preserved",
                }
            )
        )

        with patch(
            "vibe3.agents.backends.codeagent_config.MODELS_JSON_PATH",
            models_path,
        ):
            options = AgentOptions(backend="claude", model="claude-sonnet-4-6")
            sync_models_json(options)

        data = json.loads(models_path.read_text())
        assert data["default_backend"] == "claude"
        assert data["default_model"] == "claude-sonnet-4-6"
        assert data["agents"]["custom-agent"]["backend"] == "openai"
        assert data["other_field"] == "preserved"

    def test_sync_overwrites_existing_defaults(self, tmp_path: Path) -> None:
        """sync_models_json should overwrite existing default_backend/model."""
        models_path = tmp_path / ".codeagent" / "models.json"
        models_path.parent.mkdir(parents=True)
        models_path.write_text(
            json.dumps(
                {
                    "default_backend": "old-backend",
                    "default_model": "old-model",
                }
            )
        )

        with patch(
            "vibe3.agents.backends.codeagent_config.MODELS_JSON_PATH",
            models_path,
        ):
            options = AgentOptions(backend="new-backend", model="new-model")
            sync_models_json(options)

        data = json.loads(models_path.read_text())
        assert data["default_backend"] == "new-backend"
        assert data["default_model"] == "new-model"

    def test_sync_resolves_agent_preset_before_syncing(self, tmp_path: Path) -> None:
        """sync_models_json should resolve agent preset before syncing."""
        repo_models = tmp_path / "config" / "models.json"
        repo_models.parent.mkdir(parents=True)
        repo_models.write_text(
            json.dumps({"agents": {"test-agent": {"backend": "resolved-backend"}}})
        )

        codeagent_models = tmp_path / ".codeagent" / "models.json"

        with (
            patch(
                "vibe3.agents.backends.codeagent_config.repo_models_json_path",
                return_value=repo_models,
            ),
            patch(
                "vibe3.agents.backends.codeagent_config.MODELS_JSON_PATH",
                codeagent_models,
            ),
        ):
            options = AgentOptions(agent="test-agent")
            sync_models_json(options)

        data = json.loads(codeagent_models.read_text())
        assert data["default_backend"] == "resolved-backend"
