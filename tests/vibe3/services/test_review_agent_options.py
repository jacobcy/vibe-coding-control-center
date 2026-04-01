"""Tests for AgentOptions dataclass and resolve_agent_options logic."""

import json
from dataclasses import FrozenInstanceError
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vibe3.agents.review_runner import sync_models_json
from vibe3.models.review_runner import AgentOptions


class TestAgentOptions:
    """Tests for AgentOptions dataclass - immutable configuration."""

    def test_default_options(self) -> None:
        """Default options should have None for agent/backend/model."""
        options = AgentOptions()
        assert options.agent is None
        assert options.model is None
        assert options.backend is None
        assert options.worktree is False
        assert options.timeout_seconds == 600

    def test_custom_options_with_agent(self) -> None:
        """Agent preset mode: model and backend are None."""
        options = AgentOptions(agent="code-reviewer", timeout_seconds=300)
        assert options.agent == "code-reviewer"
        assert options.model is None
        assert options.backend is None
        assert options.timeout_seconds == 300

    def test_custom_options_with_backend(self) -> None:
        """Backend mode: agent is None, model is optional."""
        options = AgentOptions(backend="claude", model="claude-3-opus")
        assert options.agent is None
        assert options.backend == "claude"
        assert options.model == "claude-3-opus"

    def test_backend_without_model(self) -> None:
        """Backend mode without model: codeagent uses backend's default."""
        options = AgentOptions(backend="claude")
        assert options.backend == "claude"
        assert options.model is None

    def test_options_are_frozen(self) -> None:
        """Options should be immutable (frozen dataclass)."""
        options = AgentOptions()
        with pytest.raises(FrozenInstanceError):
            options.agent = "other"  # type: ignore

    def test_model_meaningless_in_agent_mode(self) -> None:
        """In agent preset mode model is not used (preset defines it)."""
        # The dataclass allows it but resolve_agent_options never produces this
        options = AgentOptions(agent="code-reviewer", model="claude-3-opus")
        assert options.agent == "code-reviewer"
        # model field exists in dataclass but is ignored by run_review_agent
        assert options.model == "claude-3-opus"


class TestResolveAgentOptions:
    """Tests for CodeagentExecutionService.resolve_agent_options."""

    def _make_service(self, agent=None, backend=None, model=None):
        from vibe3.agents.runner import CodeagentExecutionService
        from vibe3.config.settings import AgentConfig, VibeConfig

        cfg = MagicMock(spec=VibeConfig)
        section_cfg = MagicMock()
        section_cfg.agent_config = AgentConfig(
            agent=agent, backend=backend, model=model
        )
        cfg.run = section_cfg
        cfg.plan = section_cfg
        cfg.review = section_cfg
        return CodeagentExecutionService(config=cfg)

    def test_cli_agent_wins_over_all(self) -> None:
        """CLI --agent has highest priority; model is irrelevant."""
        svc = self._make_service(backend="claude", model="claude-opus")
        opts = svc.resolve_agent_options("run", agent="my-preset")
        assert opts.agent == "my-preset"
        assert opts.backend is None
        assert opts.model is None

    def test_cli_backend_uses_cli_model_only(self) -> None:
        """CLI --backend does NOT inherit config model — be explicit."""
        svc = self._make_service(backend="claude", model="claude-opus")
        opts = svc.resolve_agent_options("run", backend="codex", model="gpt-5")
        assert opts.agent is None
        assert opts.backend == "codex"
        assert opts.model == "gpt-5"

    def test_cli_backend_without_model_stays_none(self) -> None:
        """CLI --backend with no --model: no config_model fallback."""
        svc = self._make_service(backend="claude", model="claude-opus")
        opts = svc.resolve_agent_options("run", backend="codex")
        assert opts.backend == "codex"
        assert opts.model is None  # NOT "claude-opus" from config

    def test_config_agent_no_model(self) -> None:
        """Config agent: model is not carried through."""
        svc = self._make_service(agent="code-reviewer")
        opts = svc.resolve_agent_options("run")
        assert opts.agent == "code-reviewer"
        assert opts.model is None
        assert opts.backend is None

    def test_config_backend_uses_config_model(self) -> None:
        """Config backend: config model IS used as the intended default."""
        svc = self._make_service(backend="claude", model="claude-sonnet-4-5")
        opts = svc.resolve_agent_options("run")
        assert opts.backend == "claude"
        assert opts.model == "claude-sonnet-4-5"

    def test_config_backend_without_model(self) -> None:
        """Config backend with no config model: model stays None."""
        svc = self._make_service(backend="claude")
        opts = svc.resolve_agent_options("run")
        assert opts.backend == "claude"
        assert opts.model is None

    def test_no_config_raises(self) -> None:
        """No agent or backend anywhere → ValueError."""
        svc = self._make_service()
        with pytest.raises(ValueError, match="No agent configuration"):
            svc.resolve_agent_options("run")

    def test_worktree_flag_propagated(self) -> None:
        """--worktree flag is passed through regardless of mode."""
        svc = self._make_service(agent="code-reviewer")
        opts = svc.resolve_agent_options("run", worktree=True)
        assert opts.worktree is True


class TestSyncModelsJson:
    """Tests for sync_models_json."""

    def test_no_op_in_agent_mode(self, tmp_path: Path) -> None:
        """In agent preset mode, models.json is not touched."""
        fake_models = tmp_path / "models.json"
        fake_models.write_text('{"default_backend": "old"}')

        with patch("vibe3.agents.backends.codeagent.MODELS_JSON_PATH", fake_models):
            sync_models_json(AgentOptions(agent="code-reviewer"))

        # file unchanged
        assert json.loads(fake_models.read_text())["default_backend"] == "old"

    def test_updates_default_backend_and_model(self, tmp_path: Path) -> None:
        """Backend mode: updates default_backend and default_model."""
        fake_models = tmp_path / "models.json"
        fake_models.write_text(
            json.dumps({"default_backend": "old", "backends": {"old": {}}})
        )

        with patch("vibe3.agents.backends.codeagent.MODELS_JSON_PATH", fake_models):
            sync_models_json(AgentOptions(backend="claude", model="claude-sonnet-4-5"))

        data = json.loads(fake_models.read_text())
        assert data["default_backend"] == "claude"
        assert data["default_model"] == "claude-sonnet-4-5"
        assert data["backends"] == {"old": {}}  # existing keys preserved

    def test_updates_backend_without_model(self, tmp_path: Path) -> None:
        """Backend without model: only default_backend is updated."""
        fake_models = tmp_path / "models.json"
        fake_models.write_text(
            json.dumps({"default_backend": "old", "default_model": "old-model"})
        )

        with patch("vibe3.agents.backends.codeagent.MODELS_JSON_PATH", fake_models):
            sync_models_json(AgentOptions(backend="codex"))

        data = json.loads(fake_models.read_text())
        assert data["default_backend"] == "codex"
        assert data["default_model"] == "old-model"  # not overwritten

    def test_creates_file_if_missing(self, tmp_path: Path) -> None:
        """Creates models.json from scratch if it doesn't exist."""
        fake_models = tmp_path / "new" / "models.json"

        with patch("vibe3.agents.backends.codeagent.MODELS_JSON_PATH", fake_models):
            sync_models_json(AgentOptions(backend="claude", model="claude-opus"))

        assert fake_models.exists()
        data = json.loads(fake_models.read_text())
        assert data["default_backend"] == "claude"
        assert data["default_model"] == "claude-opus"

    def test_tolerates_corrupt_existing_file(self, tmp_path: Path) -> None:
        """Corrupt models.json is replaced cleanly."""
        fake_models = tmp_path / "models.json"
        fake_models.write_text("NOT JSON {{{{")

        with patch("vibe3.agents.backends.codeagent.MODELS_JSON_PATH", fake_models):
            sync_models_json(AgentOptions(backend="claude", model="claude-opus"))

        data = json.loads(fake_models.read_text())
        assert data["default_backend"] == "claude"
