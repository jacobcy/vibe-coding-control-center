"""Tests for manager gemini backend integration.

Tests that manager correctly resolves the explore preset to gemini backend
and that backend appears in session logs.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

from vibe3.agents.backends.codeagent import CodeagentBackend
from vibe3.agents.backends.codeagent_config import resolve_repo_agent_preset
from vibe3.models.review_runner import AgentOptions


class TestExplorePresetResolution:
    """Tests for explore preset resolution to gemini backend."""

    def test_explore_preset_resolves_to_gemini_backend(self, tmp_path: Path) -> None:
        """resolve_repo_agent_preset should return gemini backend for explore preset."""
        repo_models = tmp_path / "config" / "models.json"
        repo_models.parent.mkdir(parents=True)
        repo_models.write_text("""{
  "agents": {
    "explore": {
      "backend": "gemini",
      "model": "gemini-3.1-pro-preview",
      "description": "Exploration agent for code investigation using Gemini"
    }
  }
}""")

        with patch(
            "vibe3.agents.backends.codeagent_config.repo_models_json_path",
            return_value=repo_models,
        ):
            result = resolve_repo_agent_preset("explore")

        assert result == ("gemini", "gemini-3.1-pro-preview")


class TestManagerBackendInSessionLog:
    """Tests for backend marker appearing in session logs."""

    def test_manager_backend_appears_in_session_log(self, tmp_path: Path) -> None:
        """Session log should show Backend: gemini when using explore preset."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = (
            "[codeagent-wrapper]\n"
            "  Backend: gemini\n"
            "  Model: gemini-3.1-pro-preview\n"
            "VERDICT: PASS\n"
        )
        mock_result.stderr = ""
        repo_models = tmp_path / "config" / "models.json"
        repo_models.parent.mkdir(parents=True)
        repo_models.write_text("""{
  "agents": {
    "explore": {
      "backend": "gemini",
      "model": "gemini-3.1-pro-preview",
      "description": "Exploration agent for code investigation using Gemini"
    }
  }
}""")

        with (
            patch.object(CodeagentBackend, "_run_subprocess") as mock_run,
            patch(
                "vibe3.agents.backends.codeagent_config.REPO_MODELS_JSON_PATH",
                repo_models,
            ),
        ):
            mock_run.return_value = (mock_result, None)
            options = AgentOptions(agent="explore")
            backend = CodeagentBackend()
            result = backend.run("prompt body", options)

        assert result.exit_code == 0
        assert "Backend: gemini" in result.stdout

        # Verify command includes gemini backend
        call_args = mock_run.call_args
        command = call_args[0][0]
        assert "--backend" in command
        assert "gemini" in command
        assert "--model" in command
        assert "gemini-3.1-pro-preview" in command
