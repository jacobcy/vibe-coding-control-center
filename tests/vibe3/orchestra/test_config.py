"""Tests for Orchestra configuration."""

import tempfile
from pathlib import Path

import yaml

from vibe3.config.settings import AgentConfig, RunConfig, VibeConfig
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.runtime.agent_resolver import resolve_manager_agent_options


def test_default_config():
    config = OrchestraConfig()

    assert config.enabled is True
    assert config.polling_interval == 900
    assert config.debug_polling_interval == 60
    assert config.debug_max_ticks == 10
    assert config.debug is False
    assert config.scene_base_ref == "origin/main"
    assert config.dry_run is False
    assert config.polling.enabled is True
    assert config.governance.enabled is True
    assert config.governance.interval_ticks == 4
    assert config.governance.supervisor_file == "supervisor/orchestra.md"
    assert config.governance.prompt_template == "orchestra.governance.plan"
    assert config.governance.include_supervisor_content is True
    assert config.governance.dry_run is False
    assert config.governance.agent is None
    assert config.governance.backend is None
    assert config.governance.model is None
    assert config.supervisor_handoff.enabled is True
    assert config.supervisor_handoff.issue_label == "supervisor"
    assert config.supervisor_handoff.handoff_state_label == "state/handoff"
    assert config.supervisor_handoff.supervisor_file == "supervisor/apply.md"
    assert config.supervisor_handoff.agent is None
    assert config.supervisor_handoff.backend is None
    assert config.supervisor_handoff.model is None
    assert config.assignee_dispatch.enabled is True
    assert config.assignee_dispatch.use_worktree is True
    assert config.assignee_dispatch.agent is None
    assert config.assignee_dispatch.backend is None
    assert config.assignee_dispatch.model is None
    assert config.assignee_dispatch.supervisor_file == "supervisor/manager.md"
    assert config.assignee_dispatch.include_supervisor_content is True
    assert config.pr_review_dispatch.enabled is True
    assert config.pr_review_dispatch.async_mode is True
    assert config.pr_review_dispatch.use_worktree is False
    assert config.state_label_dispatch.enabled is True
    pid_path = config.pid_file.as_posix()
    assert pid_path.endswith("/vibe3/orchestra.pid") or pid_path.endswith(
        ".git/vibe3/orchestra.pid"
    )


def test_config_validation():
    config = OrchestraConfig(polling_interval=60, max_concurrent_flows=5)
    assert config.polling_interval == 60
    assert config.max_concurrent_flows == 5


def test_from_settings_loads_yaml_config():
    with tempfile.TemporaryDirectory() as tmpdir:
        settings_path = Path(tmpdir) / "settings.yaml"
        settings_path.write_text(
            yaml.dump(
                {
                    "orchestra": {
                        "enabled": True,
                        "polling_interval": 120,
                        "debug_polling_interval": 45,
                        "debug_max_ticks": 6,
                        "scene_base_ref": "feature/debug-base",
                        "max_concurrent_flows": 5,
                        "polling": {
                            "enabled": False,
                        },
                        "assignee_dispatch": {
                            "enabled": False,
                            "use_worktree": False,
                            "agent": "orchestra-manager",
                            "backend": "opencode",
                            "model": "custom/manager-model",
                        },
                        "pr_review_dispatch": {
                            "enabled": False,
                            "async_mode": True,
                            "use_worktree": True,
                        },
                        "state_label_dispatch": {
                            "enabled": False,
                        },
                        "governance": {
                            "enabled": True,
                            "interval_ticks": 6,
                            "supervisor_file": "supervisor/custom.md",
                            "prompt_template": "orchestra.governance.custom",
                            "include_supervisor_content": False,
                            "dry_run": True,
                            "agent": "custom-governance",
                            "backend": "claude",
                            "model": "claude-opus-4-5",
                        },
                        "supervisor_handoff": {
                            "enabled": True,
                            "issue_label": "supervisor",
                            "handoff_state_label": "state/handoff",
                            "supervisor_file": "supervisor/custom-apply.md",
                            "agent": "custom-supervisor",
                            "backend": "gemini",
                            "model": "gemini-3-flash-preview",
                        },
                    }
                }
            )
        )

        import vibe3.config.settings as settings_module

        original_get_defaults = settings_module.VibeConfig.get_defaults

        def mock_get_defaults():
            return settings_module.VibeConfig.from_yaml(settings_path)

        settings_module.VibeConfig.get_defaults = staticmethod(mock_get_defaults)

        try:
            config = OrchestraConfig.from_settings()
            assert config.polling_interval == 120
            assert config.debug_polling_interval == 45
            assert config.debug_max_ticks == 6
            assert config.scene_base_ref == "feature/debug-base"
            assert config.max_concurrent_flows == 5
            assert config.polling.enabled is False
            assert config.assignee_dispatch.enabled is False
            assert config.assignee_dispatch.use_worktree is False
            assert config.assignee_dispatch.agent == "orchestra-manager"
            assert config.assignee_dispatch.backend == "opencode"
            assert config.assignee_dispatch.model == "custom/manager-model"
            assert config.pr_review_dispatch.enabled is False
            assert config.pr_review_dispatch.async_mode is True
            assert config.pr_review_dispatch.use_worktree is True
            assert config.state_label_dispatch.enabled is False
            assert config.governance.enabled is True
            assert config.governance.interval_ticks == 6
            assert config.governance.supervisor_file == "supervisor/custom.md"
            assert config.governance.prompt_template == "orchestra.governance.custom"
            assert config.governance.include_supervisor_content is False
            assert config.governance.dry_run is True
            assert config.governance.agent == "custom-governance"
            assert config.governance.backend == "claude"
            assert config.governance.model == "claude-opus-4-5"
            assert config.supervisor_handoff.enabled is True
            assert config.supervisor_handoff.issue_label == "supervisor"
            assert config.supervisor_handoff.handoff_state_label == "state/handoff"
            assert (
                config.supervisor_handoff.supervisor_file
                == "supervisor/custom-apply.md"
            )
            assert config.supervisor_handoff.agent == "custom-supervisor"
            assert config.supervisor_handoff.backend == "gemini"
            assert config.supervisor_handoff.model == "gemini-3-flash-preview"
        finally:
            settings_module.VibeConfig.get_defaults = original_get_defaults


def test_from_settings_normalizes_empty_repo_to_none():
    with tempfile.TemporaryDirectory() as tmpdir:
        settings_path = Path(tmpdir) / "settings.yaml"
        settings_path.write_text(
            yaml.dump(
                {
                    "orchestra": {
                        "enabled": True,
                        "repo": "",
                    }
                }
            )
        )

        import vibe3.config.settings as settings_module

        original_get_defaults = settings_module.VibeConfig.get_defaults

        def mock_get_defaults():
            return settings_module.VibeConfig.from_yaml(settings_path)

        settings_module.VibeConfig.get_defaults = staticmethod(mock_get_defaults)

        try:
            config = OrchestraConfig.from_settings()
            assert config.repo is None
        finally:
            settings_module.VibeConfig.get_defaults = original_get_defaults


def test_from_settings_does_not_invent_agent_presets_when_yaml_omits_them():
    with tempfile.TemporaryDirectory() as tmpdir:
        settings_path = Path(tmpdir) / "settings.yaml"
        settings_path.write_text(
            yaml.dump(
                {
                    "orchestra": {
                        "enabled": True,
                        "assignee_dispatch": {
                            "enabled": True,
                            "use_worktree": True,
                        },
                        "governance": {
                            "enabled": True,
                        },
                        "supervisor_handoff": {
                            "enabled": True,
                        },
                    }
                }
            )
        )

        import vibe3.config.settings as settings_module

        original_get_defaults = settings_module.VibeConfig.get_defaults

        def mock_get_defaults():
            return settings_module.VibeConfig.from_yaml(settings_path)

        settings_module.VibeConfig.get_defaults = staticmethod(mock_get_defaults)

        try:
            config = OrchestraConfig.from_settings()
            assert config.assignee_dispatch.agent is None
            assert config.governance.agent is None
            assert config.supervisor_handoff.agent is None
        finally:
            settings_module.VibeConfig.get_defaults = original_get_defaults


def test_manager_agent_resolution_falls_back_to_run_config(monkeypatch):
    monkeypatch.setattr(
        "vibe3.runtime.agent_resolver.resolve_effective_agent_options",
        lambda options: options,
    )
    monkeypatch.setattr(
        "vibe3.runtime.agent_resolver.sync_models_json",
        lambda options: None,
    )

    runtime = VibeConfig(
        run=RunConfig(agent_config=AgentConfig(agent="develop")),
    )
    config = OrchestraConfig()

    options = resolve_manager_agent_options(config, runtime)

    assert options.agent == "develop"
    assert options.backend is None
    assert options.model is None


def test_manager_agent_resolution_supports_backend_only_override(monkeypatch):
    monkeypatch.setattr(
        "vibe3.runtime.agent_resolver.resolve_effective_agent_options",
        lambda options: options,
    )
    monkeypatch.setattr(
        "vibe3.runtime.agent_resolver.sync_models_json",
        lambda options: None,
    )

    runtime = VibeConfig(
        run=RunConfig(agent_config=AgentConfig(agent="develop")),
    )
    config = OrchestraConfig.model_validate(
        {
            "assignee_dispatch": {
                "backend": "opencode",
                "model": "alibaba-coding-plan-cn/glm-5",
            }
        }
    )

    options = resolve_manager_agent_options(config, runtime)

    assert options.agent is None
    assert options.backend == "opencode"
    assert options.model == "alibaba-coding-plan-cn/glm-5"


def test_manager_timeout_defaults_to_1800_seconds():
    """Manager should have a longer default timeout for long-running tasks."""
    config = OrchestraConfig()

    assert config.assignee_dispatch.timeout_seconds == 1800


def test_resolve_manager_agent_options_uses_orchestra_timeout_override():
    """Manager agent options should use orchestra config timeout."""
    config = OrchestraConfig()
    runtime = VibeConfig(
        run=RunConfig(agent_config=AgentConfig(agent="develop")),
    )

    options = resolve_manager_agent_options(config, runtime)

    assert options.timeout_seconds == 1800
