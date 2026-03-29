"""Tests for Orchestra configuration."""

import tempfile
from pathlib import Path

import yaml

from vibe3.models.orchestration import IssueState
from vibe3.orchestra.config import STATE_TRIGGERS, MasterAgentConfig, OrchestraConfig


def test_default_config():
    assert OrchestraConfig().enabled is True
    assert OrchestraConfig().polling_interval == 900
    assert OrchestraConfig().dry_run is False
    assert OrchestraConfig().polling.enabled is True
    assert OrchestraConfig().assignee_dispatch.enabled is True
    assert OrchestraConfig().pr_review_dispatch.enabled is True
    assert OrchestraConfig().pr_review_dispatch.async_mode is False
    pid_path = OrchestraConfig().pid_file.as_posix()
    assert pid_path.endswith("/vibe3/orchestra.pid") or pid_path.endswith(
        ".git/vibe3/orchestra.pid"
    )


def test_config_validation():
    config = OrchestraConfig(polling_interval=60, max_concurrent_flows=5)
    assert config.polling_interval == 60
    assert config.max_concurrent_flows == 5


def test_state_triggers_defined():
    assert len(STATE_TRIGGERS) == 3

    trigger_names = [(t.from_state, t.to_state, t.command) for t in STATE_TRIGGERS]
    assert (IssueState.READY, IssueState.CLAIMED, "plan") in trigger_names
    assert (IssueState.CLAIMED, IssueState.IN_PROGRESS, "run") in trigger_names
    assert (IssueState.IN_PROGRESS, IssueState.REVIEW, "review") in trigger_names


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
                        },
                        "pr_review_dispatch": {
                            "enabled": False,
                            "async_mode": True,
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
            assert config.max_concurrent_flows == 5
            assert config.master_agent.agent == "test-controller"
            assert config.master_agent.timeout_seconds == 600
            assert config.polling.enabled is False
            assert config.assignee_dispatch.enabled is False
            assert config.pr_review_dispatch.enabled is False
            assert config.pr_review_dispatch.async_mode is True
        finally:
            settings_module.VibeConfig.get_defaults = original_get_defaults
