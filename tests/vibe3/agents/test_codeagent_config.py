"""Tests for codeagent_config agent resolution and models.json sync.

Core contract tests for resolve_effective_agent_options, sync_models_json,
and VIBE3_REPO_MODELS_ROOT override.
"""

import json
import os
from pathlib import Path
from unittest.mock import patch

from vibe3.agents.backends.codeagent_config import (
    resolve_effective_agent_options,
    resolve_repo_agent_preset,
    sync_models_json,
)
from vibe3.models.review_runner import AgentOptions


class TestResolveEffectiveAgentOptions:
    """Tests for resolve_effective_agent_options priority logic."""

    def test_explicit_backend_returns_unchanged(self) -> None:
        """Explicit backend should return options unchanged."""
        options = AgentOptions(backend="claude", model="claude-sonnet-4-6")
        result = resolve_effective_agent_options(options)
        assert result.backend == "claude"
        assert result.model == "claude-sonnet-4-6"
        assert result.agent is None

    def test_agent_preset_resolved_from_repo_models(self, tmp_path: Path) -> None:
        """Agent preset should resolve from repo-local models.json."""
        repo_models = tmp_path / "config" / "models.json"
        repo_models.parent.mkdir(parents=True)
        repo_models.write_text(
            json.dumps(
                {
                    "agents": {
                        "code-reviewer": {
                            "backend": "claude",
                            "model": "claude-sonnet-4-6",
                        }
                    }
                }
            )
        )

        with patch(
            "vibe3.agents.backends.codeagent_config.repo_models_json_path",
            return_value=repo_models,
        ):
            options = AgentOptions(agent="code-reviewer")
            result = resolve_effective_agent_options(options)

        assert result.backend == "claude"
        assert result.model == "claude-sonnet-4-6"
        assert result.agent is None

    def test_agent_preset_fallback_when_no_mapping(self) -> None:
        """Agent preset without mapping should return unchanged."""
        options = AgentOptions(agent="unknown-preset")
        result = resolve_effective_agent_options(options)
        assert result.agent == "unknown-preset"
        assert result.backend is None
        assert result.model is None

    def test_agent_preset_model_override(self, tmp_path: Path) -> None:
        """Agent preset with explicit model override should use override."""
        repo_models = tmp_path / "config" / "models.json"
        repo_models.parent.mkdir(parents=True)
        repo_models.write_text(
            json.dumps(
                {
                    "agents": {
                        "code-reviewer": {
                            "backend": "claude",
                            "model": "claude-sonnet-4-6",
                        }
                    }
                }
            )
        )

        with patch(
            "vibe3.agents.backends.codeagent_config.repo_models_json_path",
            return_value=repo_models,
        ):
            options = AgentOptions(agent="code-reviewer", model="claude-opus-4-6")
            result = resolve_effective_agent_options(options)

        assert result.backend == "claude"
        assert result.model == "claude-opus-4-6"  # Override wins

    def test_agent_preset_backend_only(self, tmp_path: Path) -> None:
        """Agent preset with backend only should resolve correctly."""
        repo_models = tmp_path / "config" / "models.json"
        repo_models.parent.mkdir(parents=True)
        repo_models.write_text(
            json.dumps({"agents": {"minimal-agent": {"backend": "gemini"}}})
        )

        with patch(
            "vibe3.agents.backends.codeagent_config.repo_models_json_path",
            return_value=repo_models,
        ):
            options = AgentOptions(agent="minimal-agent")
            result = resolve_effective_agent_options(options)

        assert result.backend == "gemini"
        assert result.model is None

    def test_empty_agent_returns_unchanged(self) -> None:
        """Empty agent should return unchanged options."""
        options = AgentOptions()
        result = resolve_effective_agent_options(options)
        assert result.agent is None
        assert result.backend is None
        assert result.model is None


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
        """sync_models_json should skip when backend is None."""
        models_path = tmp_path / ".codeagent" / "models.json"

        with patch(
            "vibe3.agents.backends.codeagent_config.MODELS_JSON_PATH",
            models_path,
        ):
            options = AgentOptions(agent="some-preset")
            sync_models_json(options)

        # Should not create file
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
        """With VIBE3_REPO_MODELS_ROOT, resolve to override/config/models.json."""
        override_root = tmp_path / "custom_root"
        expected_path = override_root / "config" / "models.json"

        with patch.dict(
            os.environ,
            {"VIBE3_REPO_MODELS_ROOT": str(override_root)},
            clear=True,
        ):
            from vibe3.agents.backends.codeagent_config import repo_models_json_path

            result = repo_models_json_path()

        assert result == expected_path

    def test_override_supports_tilde_expansion(self, tmp_path: Path) -> None:
        """VIBE3_REPO_MODELS_ROOT should support ~ expansion."""
        # Use a path with ~ that expands to home directory
        home_based = "~/custom-vibe-root"
        expected_base = Path(home_based).expanduser()
        expected_path = expected_base / "config" / "models.json"

        with patch.dict(
            os.environ,
            {"VIBE3_REPO_MODELS_ROOT": home_based},
            clear=True,
        ):
            from vibe3.agents.backends.codeagent_config import repo_models_json_path

            result = repo_models_json_path()

        assert result == expected_path

    def test_override_resolves_to_absolute_path(self, tmp_path: Path) -> None:
        """VIBE3_REPO_MODELS_ROOT should resolve to absolute path."""
        relative_path = "../custom-root"
        expected_base = Path(relative_path).expanduser().resolve()
        expected_path = expected_base / "config" / "models.json"

        with patch.dict(
            os.environ,
            {"VIBE3_REPO_MODELS_ROOT": relative_path},
            clear=True,
        ):
            from vibe3.agents.backends.codeagent_config import repo_models_json_path

            result = repo_models_json_path()

        assert result == expected_path
        assert result.is_absolute()


class TestResolveRepoAgentPreset:
    """Tests for resolve_repo_agent_preset reading from repo models.json."""

    def test_preset_resolution_returns_backend_and_model(self, tmp_path: Path) -> None:
        """resolve_repo_agent_preset should return (backend, model) tuple."""
        repo_models = tmp_path / "config" / "models.json"
        repo_models.parent.mkdir(parents=True)
        repo_models.write_text(
            json.dumps(
                {
                    "agents": {
                        "test-preset": {
                            "backend": "claude",
                            "model": "claude-sonnet-4-6",
                        }
                    }
                }
            )
        )

        with patch(
            "vibe3.agents.backends.codeagent_config.repo_models_json_path",
            return_value=repo_models,
        ):
            result = resolve_repo_agent_preset("test-preset")

        assert result == ("claude", "claude-sonnet-4-6")

    def test_preset_not_found_returns_none(self, tmp_path: Path) -> None:
        """resolve_repo_agent_preset should return None for unknown preset."""
        repo_models = tmp_path / "config" / "models.json"
        repo_models.parent.mkdir(parents=True)
        repo_models.write_text(json.dumps({"agents": {}}))

        with patch(
            "vibe3.agents.backends.codeagent_config.repo_models_json_path",
            return_value=repo_models,
        ):
            result = resolve_repo_agent_preset("unknown-preset")

        assert result is None

    def test_preset_backend_only(self, tmp_path: Path) -> None:
        """resolve_repo_agent_preset should handle backend-only preset."""
        repo_models = tmp_path / "config" / "models.json"
        repo_models.parent.mkdir(parents=True)
        repo_models.write_text(
            json.dumps({"agents": {"minimal": {"backend": "gemini"}}})
        )

        with patch(
            "vibe3.agents.backends.codeagent_config.repo_models_json_path",
            return_value=repo_models,
        ):
            result = resolve_repo_agent_preset("minimal")

        assert result == ("gemini", None)

    def test_preset_missing_agents_key_returns_none(self, tmp_path: Path) -> None:
        """resolve_repo_agent_preset should return None when agents key missing."""
        repo_models = tmp_path / "config" / "models.json"
        repo_models.parent.mkdir(parents=True)
        repo_models.write_text(json.dumps({}))

        with patch(
            "vibe3.agents.backends.codeagent_config.repo_models_json_path",
            return_value=repo_models,
        ):
            result = resolve_repo_agent_preset("any-preset")

        assert result is None

    def test_preset_file_not_exists_returns_none(self, tmp_path: Path) -> None:
        """resolve_repo_agent_preset should return None when file doesn't exist."""
        repo_models = tmp_path / "config" / "models.json"

        with patch(
            "vibe3.agents.backends.codeagent_config.repo_models_json_path",
            return_value=repo_models,
        ):
            result = resolve_repo_agent_preset("any-preset")

        assert result is None
