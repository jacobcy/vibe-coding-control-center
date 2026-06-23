"""Tests for common.py command layer utilities."""

from unittest.mock import patch

import pytest

from vibe3.commands.common import _resolve_dry_run_actor, echo_dry_run_header


class TestResolveDryRunActor:
    """Tests for _resolve_dry_run_actor helper function."""

    def test_explicit_backend_model(self) -> None:
        """When backend/model are explicitly provided, return them formatted."""
        result = _resolve_dry_run_actor(
            role="planner",
            agent=None,
            backend="claude",
            model="sonnet",
        )
        assert result == "claude/sonnet"

    def test_explicit_agent_preset_resolved(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When agent preset is provided and configured, return resolved backend/model."""  # noqa: E501
        # Clear env vars that could override agent preset resolution
        monkeypatch.delenv("VIBE_BACKEND_PLANNER", raising=False)
        monkeypatch.delenv("VIBE_MODEL_PLANNER", raising=False)

        mock_data = {
            "agents": {
                "vibe-planner": {"backend": "claude", "model": "sonnet"},
            },
        }
        with (
            patch("vibe3.config.read_models_json", return_value=mock_data),
            patch(
                "vibe3.config.repo_models_json_path",
                return_value="/fake/path/models.json",
            ),
        ):
            result = _resolve_dry_run_actor(
                role="planner",
                agent="vibe-planner",
                backend=None,
                model=None,
            )
        assert result == "claude/sonnet"

    def test_no_flags_with_configured_defaults(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When no flags provided and repo has defaults, return configured defaults."""
        # Clear env vars that could override default resolution
        monkeypatch.delenv("VIBE_DEFAULT_BACKEND", raising=False)
        monkeypatch.delenv("VIBE_DEFAULT_MODEL", raising=False)

        mock_data = {
            "default_backend": "claude",
            "default_model": "haiku",
        }
        with (
            patch("vibe3.config.read_models_json", return_value=mock_data),
            patch(
                "vibe3.config.repo_models_json_path",
                return_value="/fake/path/models.json",
            ),
        ):
            result = _resolve_dry_run_actor(
                role="planner",
                agent=None,
                backend=None,
                model=None,
            )
        assert result == "claude/haiku"

    def test_no_flags_no_defaults_returns_role_default(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When no flags and no defaults configured, return role default."""
        # Clear env vars that could provide defaults
        monkeypatch.delenv("VIBE_DEFAULT_BACKEND", raising=False)
        monkeypatch.delenv("VIBE_DEFAULT_MODEL", raising=False)

        mock_data: dict[str, str] = {}
        with (
            patch("vibe3.config.read_models_json", return_value=mock_data),
            patch(
                "vibe3.config.repo_models_json_path",
                return_value="/fake/path/models.json",
            ),
        ):
            result = _resolve_dry_run_actor(
                role="planner",
                agent=None,
                backend=None,
                model=None,
            )
        assert result == "vibe-planner"

    def test_no_flags_no_defaults_executor_role(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Role default for executor is vibe-executor."""
        # Clear env vars that could provide defaults
        monkeypatch.delenv("VIBE_DEFAULT_BACKEND", raising=False)
        monkeypatch.delenv("VIBE_DEFAULT_MODEL", raising=False)

        mock_data: dict[str, str] = {}
        with (
            patch("vibe3.config.read_models_json", return_value=mock_data),
            patch(
                "vibe3.config.repo_models_json_path",
                return_value="/fake/path/models.json",
            ),
        ):
            result = _resolve_dry_run_actor(
                role="executor",
                agent=None,
                backend=None,
                model=None,
            )
        assert result == "vibe-executor"

    def test_no_flags_no_defaults_reviewer_role(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Role default for reviewer is vibe-reviewer."""
        # Clear env vars that could provide defaults
        monkeypatch.delenv("VIBE_DEFAULT_BACKEND", raising=False)
        monkeypatch.delenv("VIBE_DEFAULT_MODEL", raising=False)

        mock_data: dict[str, str] = {}
        with (
            patch("vibe3.config.read_models_json", return_value=mock_data),
            patch(
                "vibe3.config.repo_models_json_path",
                return_value="/fake/path/models.json",
            ),
        ):
            result = _resolve_dry_run_actor(
                role="reviewer",
                agent=None,
                backend=None,
                model=None,
            )
        assert result == "vibe-reviewer"

    def test_agent_preset_not_found_returns_agent_name(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When agent preset is provided but not found, return agent name as-is."""
        # Clear env vars that could provide fallback defaults
        monkeypatch.delenv("VIBE_DEFAULT_BACKEND", raising=False)
        monkeypatch.delenv("VIBE_DEFAULT_MODEL", raising=False)

        mock_data: dict[str, str] = {}
        # Need to mock both import locations since resolve_effective_agent_options
        # imports directly from agent_preset module
        with (
            patch("vibe3.config.read_models_json", return_value=mock_data),
            patch("vibe3.config.agent_preset.read_models_json", return_value=mock_data),
            patch(
                "vibe3.config.repo_models_json_path",
                return_value="/fake/path/models.json",
            ),
        ):
            result = _resolve_dry_run_actor(
                role="planner",
                agent="unknown-preset",
                backend=None,
                model=None,
            )
        assert result == "unknown-preset"

    def test_default_model_missing_still_formats_backend(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When default_backend exists but default_model is missing, format backend only."""  # noqa: E501
        # Clear env vars that could provide defaults
        monkeypatch.delenv("VIBE_DEFAULT_BACKEND", raising=False)
        monkeypatch.delenv("VIBE_DEFAULT_MODEL", raising=False)

        mock_data = {
            "default_backend": "claude",
        }
        with (
            patch("vibe3.config.read_models_json", return_value=mock_data),
            patch(
                "vibe3.config.repo_models_json_path",
                return_value="/fake/path/models.json",
            ),
        ):
            result = _resolve_dry_run_actor(
                role="planner",
                agent=None,
                backend=None,
                model=None,
            )
        assert result == "claude"

    def test_default_backend_whitespace_falls_back_to_role_default(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When default_backend is whitespace-only, fall back to role default."""
        # Clear env vars that could provide defaults
        monkeypatch.delenv("VIBE_DEFAULT_BACKEND", raising=False)
        monkeypatch.delenv("VIBE_DEFAULT_MODEL", raising=False)

        mock_data = {
            "default_backend": "   ",  # whitespace-only
            "default_model": "haiku",
        }
        with (
            patch("vibe3.config.read_models_json", return_value=mock_data),
            patch(
                "vibe3.config.repo_models_json_path",
                return_value="/fake/path/models.json",
            ),
        ):
            result = _resolve_dry_run_actor(
                role="planner",
                agent=None,
                backend=None,
                model=None,
            )
        assert result == "vibe-planner"

    def test_default_backend_non_string_falls_back_to_role_default(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When default_backend is non-string (e.g. int), fall back to role default."""
        # Clear env vars that could provide defaults
        monkeypatch.delenv("VIBE_DEFAULT_BACKEND", raising=False)
        monkeypatch.delenv("VIBE_DEFAULT_MODEL", raising=False)

        mock_data = {
            "default_backend": 123,  # non-string type
            "default_model": "haiku",
        }
        with (
            patch("vibe3.config.read_models_json", return_value=mock_data),
            patch(
                "vibe3.config.repo_models_json_path",
                return_value="/fake/path/models.json",
            ),
        ):
            result = _resolve_dry_run_actor(
                role="planner",
                agent=None,
                backend=None,
                model=None,
            )
        assert result == "vibe-planner"


class TestEchoDryRunHeader:
    """Tests for echo_dry_run_header command function."""

    def test_echo_with_configured_defaults(
        self, capsys: pytest.CaptureFixture, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When no flags provided, header uses configured defaults."""
        # Clear env vars that could provide defaults
        monkeypatch.delenv("VIBE_DEFAULT_BACKEND", raising=False)
        monkeypatch.delenv("VIBE_DEFAULT_MODEL", raising=False)

        mock_data = {
            "default_backend": "claude",
            "default_model": "haiku",
        }
        with (
            patch("vibe3.config.read_models_json", return_value=mock_data),
            patch(
                "vibe3.config.repo_models_json_path",
                return_value="/fake/path/models.json",
            ),
        ):
            echo_dry_run_header(
                role="planner",
                issue_number=42,
                branch="task/issue-42",
                agent=None,
                backend=None,
                model=None,
            )

        captured = capsys.readouterr()
        assert "-> planner run: issue #42 (dry-run)" in captured.out
        assert "branch: task/issue-42" in captured.out
        assert "actor:  claude/haiku" in captured.out

    def test_echo_with_explicit_backend_model(
        self, capsys: pytest.CaptureFixture
    ) -> None:
        """When backend/model explicitly provided, header shows them."""
        echo_dry_run_header(
            role="executor",
            issue_number=10,
            branch="task/issue-10",
            agent=None,
            backend="gemini",
            model="gemini-pro",
        )

        captured = capsys.readouterr()
        assert "-> executor run: issue #10 (dry-run)" in captured.out
        assert "actor:  gemini/gemini-pro" in captured.out
