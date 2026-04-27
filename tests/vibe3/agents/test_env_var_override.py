"""Tests for environment variable override of models.json config."""

import json
import os
from pathlib import Path
from unittest.mock import patch

from vibe3.agents.backends.codeagent_config import (
    resolve_effective_agent_options,
    resolve_repo_agent_preset,
)
from vibe3.models.review_runner import AgentOptions


class TestEnvVarOverride:
    """Tests for environment variable override of models.json config."""

    def test_agent_backend_env_override(self, tmp_path: Path) -> None:
        """VIBE_BACKEND_<ROLE> should override models.json agent config."""
        repo_models = tmp_path / "config" / "models.json"
        repo_models.parent.mkdir(parents=True)
        repo_models.write_text(
            json.dumps(
                {
                    "agents": {
                        "vibe-manager": {
                            "backend": "gemini",
                            "model": "gemini-3-flash-preview",
                        }
                    }
                }
            )
        )

        with (
            patch(
                "vibe3.agents.backends.codeagent_config.repo_models_json_path",
                return_value=repo_models,
            ),
            patch.dict(
                os.environ,
                {"VIBE_BACKEND_MANAGER": "claude"},
                clear=True,
            ),
        ):
            result = resolve_repo_agent_preset("vibe-manager")

        assert result == ("claude", None)

    def test_agent_model_env_override(self, tmp_path: Path) -> None:
        """VIBE_MODEL_<ROLE> should override models.json agent config."""
        repo_models = tmp_path / "config" / "models.json"
        repo_models.parent.mkdir(parents=True)
        repo_models.write_text(
            json.dumps(
                {
                    "agents": {
                        "vibe-planner": {
                            "backend": "claude",
                            "model": "haiku",
                        }
                    }
                }
            )
        )

        with (
            patch(
                "vibe3.agents.backends.codeagent_config.repo_models_json_path",
                return_value=repo_models,
            ),
            patch.dict(
                os.environ,
                {"VIBE_MODEL_PLANNER": "sonnet"},
                clear=True,
            ),
        ):
            result = resolve_repo_agent_preset("vibe-planner")

        assert result == (None, "sonnet")

    def test_agent_both_env_override(self, tmp_path: Path) -> None:
        """Both VIBE_BACKEND_<ROLE> and VIBE_MODEL_<ROLE> should work together."""
        repo_models = tmp_path / "config" / "models.json"
        repo_models.parent.mkdir(parents=True)
        repo_models.write_text(json.dumps({"agents": {}}))

        with (
            patch(
                "vibe3.agents.backends.codeagent_config.repo_models_json_path",
                return_value=repo_models,
            ),
            patch.dict(
                os.environ,
                {
                    "VIBE_BACKEND_EXECUTOR": "codex",
                    "VIBE_MODEL_EXECUTOR": "gpt-5.4",
                },
                clear=True,
            ),
        ):
            result = resolve_repo_agent_preset("vibe-executor")

        assert result == ("codex", "gpt-5.4")

    def test_env_override_without_vibe_prefix(self, tmp_path: Path) -> None:
        """Env override should work with agent names without vibe- prefix."""
        repo_models = tmp_path / "config" / "models.json"
        repo_models.parent.mkdir(parents=True)
        repo_models.write_text(json.dumps({"agents": {}}))

        with (
            patch(
                "vibe3.agents.backends.codeagent_config.repo_models_json_path",
                return_value=repo_models,
            ),
            patch.dict(
                os.environ,
                {"VIBE_BACKEND_REVIEWER": "gemini"},
                clear=True,
            ),
        ):
            result = resolve_repo_agent_preset("reviewer")

        assert result == ("gemini", None)

    def test_default_backend_env_override(self, tmp_path: Path) -> None:
        """VIBE_DEFAULT_BACKEND should override models.json default_backend."""
        repo_models = tmp_path / "config" / "models.json"
        repo_models.parent.mkdir(parents=True)
        repo_models.write_text(
            json.dumps(
                {
                    "default_backend": "opencode",
                    "default_model": "default-model",
                }
            )
        )

        with (
            patch(
                "vibe3.agents.backends.codeagent_config.repo_models_json_path",
                return_value=repo_models,
            ),
            patch.dict(
                os.environ,
                {"VIBE_DEFAULT_BACKEND": "claude"},
                clear=True,
            ),
        ):
            options = AgentOptions(agent="unknown-preset")
            result = resolve_effective_agent_options(options)

        assert result.backend == "claude"

    def test_default_model_env_override(self, tmp_path: Path) -> None:
        """VIBE_DEFAULT_MODEL should override models.json default_model."""
        repo_models = tmp_path / "config" / "models.json"
        repo_models.parent.mkdir(parents=True)
        repo_models.write_text(
            json.dumps(
                {
                    "default_backend": "claude",
                    "default_model": "haiku",
                }
            )
        )

        with (
            patch(
                "vibe3.agents.backends.codeagent_config.repo_models_json_path",
                return_value=repo_models,
            ),
            patch.dict(
                os.environ,
                {"VIBE_DEFAULT_MODEL": "sonnet"},
                clear=True,
            ),
        ):
            options = AgentOptions(agent="unknown-preset")
            result = resolve_effective_agent_options(options)

        assert result.model == "sonnet"

    def test_env_override_priority_over_models_json(self, tmp_path: Path) -> None:
        """Env override should take priority over models.json config."""
        repo_models = tmp_path / "config" / "models.json"
        repo_models.parent.mkdir(parents=True)
        repo_models.write_text(
            json.dumps(
                {
                    "agents": {
                        "vibe-manager": {
                            "backend": "gemini",
                            "model": "gemini-3-flash",
                        }
                    }
                }
            )
        )

        with (
            patch(
                "vibe3.agents.backends.codeagent_config.repo_models_json_path",
                return_value=repo_models,
            ),
            patch.dict(
                os.environ,
                {
                    "VIBE_BACKEND_MANAGER": "claude",
                    "VIBE_MODEL_MANAGER": "sonnet",
                },
                clear=True,
            ),
        ):
            result = resolve_repo_agent_preset("vibe-manager")

        # Env override wins
        assert result == ("claude", "sonnet")
