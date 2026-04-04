"""Tests for Orchestra configuration."""

import tempfile
from pathlib import Path

import yaml

from vibe3.orchestra.config import MasterAgentConfig, OrchestraConfig


def test_default_config():
    config = OrchestraConfig()

    assert config.enabled is True
    assert config.polling_interval == 900
    assert config.debug_polling_interval == 60
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
    assert config.supervisor_handoff.enabled is True
    assert config.supervisor_handoff.issue_label == "supervisor"
    assert config.supervisor_handoff.handoff_state_label == "state/handoff"
    assert config.supervisor_handoff.supervisor_file == "supervisor/apply.md"
    assert config.assignee_dispatch.enabled is True
    assert config.assignee_dispatch.use_worktree is True
    assert config.assignee_dispatch.agent == "develop"
    assert config.assignee_dispatch.backend is None
    assert config.assignee_dispatch.model is None
    assert config.assignee_dispatch.supervisor_file == "supervisor/manager.md"
    assert config.assignee_dispatch.include_supervisor_content is True
    assert config.pr_review_dispatch.enabled is True
    assert config.pr_review_dispatch.async_mode is False
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


def test_master_agent_config():
    config = MasterAgentConfig()
    assert config.enabled is True
    assert config.agent == "master-controller"
    assert config.timeout_seconds == 300

    config_custom = MasterAgentConfig(
        enabled=False,
        agent="custom-agent",
        backend="claude",
        model="claude-sonnet-4-5",
        timeout_seconds=600,
    )
    assert config_custom.enabled is False
    assert config_custom.agent == "custom-agent"
    assert config_custom.backend == "claude"
    assert config_custom.model == "claude-sonnet-4-5"
    assert config_custom.timeout_seconds == 600


def test_orchestra_config_with_master_agent():
    master = MasterAgentConfig(enabled=False, agent="test-agent")
    config = OrchestraConfig(
        polling_interval=120,
        max_concurrent_flows=2,
        master_agent=master,
    )
    assert config.polling_interval == 120
    assert config.max_concurrent_flows == 2
    assert config.master_agent.enabled is False
    assert config.master_agent.agent == "test-agent"


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
                        "scene_base_ref": "feature/debug-base",
                        "max_concurrent_flows": 5,
                        "master_agent": {
                            "enabled": True,
                            "agent": "test-controller",
                            "timeout_seconds": 600,
                        },
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
                        },
                        "supervisor_handoff": {
                            "enabled": True,
                            "issue_label": "supervisor",
                            "handoff_state_label": "state/handoff",
                            "supervisor_file": "supervisor/custom-apply.md",
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
            assert config.scene_base_ref == "feature/debug-base"
            assert config.max_concurrent_flows == 5
            assert config.master_agent.agent == "test-controller"
            assert config.master_agent.timeout_seconds == 600
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
            assert config.supervisor_handoff.enabled is True
            assert config.supervisor_handoff.issue_label == "supervisor"
            assert config.supervisor_handoff.handoff_state_label == "state/handoff"
            assert (
                config.supervisor_handoff.supervisor_file
                == "supervisor/custom-apply.md"
            )
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
