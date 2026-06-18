"""Tests for agent preset resolution logic.

Tests resolve_effective_agent_options, resolve_repo_agent_preset,
and agent preset fallback behavior.
"""

import json
from pathlib import Path
from unittest.mock import patch

from vibe3.config.agent_preset import (
    resolve_effective_agent_options,
    resolve_repo_agent_preset,
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
                        "vibe-reviewer": {
                            "backend": "claude",
                            "model": "claude-sonnet-4-6",
                        }
                    }
                }
            )
        )

        with patch(
            "vibe3.config.agent_preset.repo_models_json_path",
            return_value=repo_models,
        ):
            options = AgentOptions(agent="vibe-reviewer")
            result = resolve_effective_agent_options(options)

        assert result.backend == "claude"
        assert result.model == "claude-sonnet-4-6"
        assert result.agent is None


class TestAgentPresetFallback:
    """Tests for agent preset fallback to default behavior."""

    def test_agent_preset_fallback_to_default_when_no_mapping(
        self, tmp_path: Path
    ) -> None:
        """Agent preset without mapping should fall back to default_backend/model."""
        repo_models = tmp_path / "config" / "models.json"
        repo_models.parent.mkdir(parents=True)
        repo_models.write_text(
            json.dumps(
                {
                    "default_backend": "claude",
                    "default_model": "claude-sonnet-4-6",
                    "agents": {},
                }
            )
        )
        with patch(
            "vibe3.config.agent_preset.REPO_MODELS_JSON_PATH",
            repo_models,
        ):
            options = AgentOptions(agent="unknown-preset")
            result = resolve_effective_agent_options(options)
        assert result.agent is None
        assert result.backend == "claude"
        assert result.model == "claude-sonnet-4-6"

    def test_agent_preset_raises_when_no_mapping_and_no_default(
        self, tmp_path: Path
    ) -> None:
        """Agent preset without mapping and no default should raise."""
        repo_models = tmp_path / "config" / "models.json"
        repo_models.parent.mkdir(parents=True)
        repo_models.write_text(json.dumps({"agents": {}}))
        with patch(
            "vibe3.config.agent_preset.REPO_MODELS_JSON_PATH",
            repo_models,
        ):
            import pytest

            from vibe3.exceptions import AgentPresetNotFoundError

            with pytest.raises(AgentPresetNotFoundError):
                resolve_effective_agent_options(AgentOptions(agent="unknown-preset"))

    def test_agent_preset_model_override(self, tmp_path: Path) -> None:
        """Agent preset with explicit model override should use override."""
        repo_models = tmp_path / "config" / "models.json"
        repo_models.parent.mkdir(parents=True)
        repo_models.write_text(
            json.dumps(
                {
                    "agents": {
                        "vibe-reviewer": {
                            "backend": "claude",
                            "model": "claude-sonnet-4-6",
                        }
                    }
                }
            )
        )

        with patch(
            "vibe3.config.agent_preset.repo_models_json_path",
            return_value=repo_models,
        ):
            options = AgentOptions(agent="vibe-reviewer", model="claude-opus-4-6")
            result = resolve_effective_agent_options(options)

        assert result.backend == "claude"
        assert result.model == "claude-opus-4-6"  # Override wins

    def test_env_model_override_preserves_preset_backend(self, tmp_path: Path) -> None:
        """Role model env override should not erase preset backend."""
        repo_models = tmp_path / "config" / "models.json"
        repo_models.parent.mkdir(parents=True)
        repo_models.write_text(
            json.dumps(
                {
                    "agents": {
                        "vibe-manager": {
                            "backend": "claude",
                            "model": "haiku",
                        }
                    }
                }
            )
        )

        with (
            patch(
                "vibe3.config.agent_preset.repo_models_json_path",
                return_value=repo_models,
            ),
            patch.dict("os.environ", {"VIBE_MODEL_MANAGER": "sonnet"}, clear=False),
        ):
            result = resolve_effective_agent_options(AgentOptions(agent="vibe-manager"))

        assert result.backend == "claude"
        assert result.model == "sonnet"

    def test_agent_preset_backend_only(self, tmp_path: Path) -> None:
        """Agent preset with backend only should resolve correctly."""
        repo_models = tmp_path / "config" / "models.json"
        repo_models.parent.mkdir(parents=True)
        repo_models.write_text(
            json.dumps({"agents": {"minimal-agent": {"backend": "gemini"}}})
        )

        with patch(
            "vibe3.config.agent_preset.repo_models_json_path",
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
            "vibe3.config.agent_preset.repo_models_json_path",
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
            "vibe3.config.agent_preset.repo_models_json_path",
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
            "vibe3.config.agent_preset.repo_models_json_path",
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
            "vibe3.config.agent_preset.repo_models_json_path",
            return_value=repo_models,
        ):
            result = resolve_repo_agent_preset("any-preset")

        assert result is None

    def test_preset_file_not_exists_returns_none(self, tmp_path: Path) -> None:
        """resolve_repo_agent_preset should return None when file doesn't exist."""
        repo_models = tmp_path / "config" / "models.json"

        with patch(
            "vibe3.config.agent_preset.repo_models_json_path",
            return_value=repo_models,
        ):
            result = resolve_repo_agent_preset("any-preset")

        assert result is None


class TestResolveAgentEntry:
    """Tests for the _resolve_agent_entry helper."""

    def test_direct_lookup(self) -> None:
        from vibe3.config.agent_preset import _resolve_agent_entry

        agents = {"reviewer": {"backend": "claude"}}
        assert _resolve_agent_entry(agents, "reviewer") == (
            "reviewer",
            {"backend": "claude"},
        )

    def test_prefixed_fallback(self) -> None:
        from vibe3.config.agent_preset import _resolve_agent_entry

        agents = {"vibe-reviewer": {"backend": "claude"}}
        assert _resolve_agent_entry(agents, "reviewer") == (
            "vibe-reviewer",
            {"backend": "claude"},
        )

    def test_not_found(self) -> None:
        from vibe3.config.agent_preset import _resolve_agent_entry

        assert _resolve_agent_entry({}, "unknown") is None

    def test_non_dict_entry_ignored(self) -> None:
        from vibe3.config.agent_preset import _resolve_agent_entry

        agents = {"reviewer": "not-a-dict"}
        assert _resolve_agent_entry(agents, "reviewer") is None
