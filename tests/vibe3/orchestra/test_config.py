"""Tests for Orchestra configuration."""

from vibe3.models.orchestration import IssueState
from vibe3.orchestra.config import STATE_TRIGGERS, OrchestraConfig


def test_default_config():
    assert OrchestraConfig().enabled is True
    assert OrchestraConfig().polling_interval == 60
    assert OrchestraConfig().dry_run is False


def test_config_validation():
    config = OrchestraConfig(polling_interval=30, max_concurrent_flows=5)
    assert config.polling_interval == 30
    assert config.max_concurrent_flows == 5


def test_state_triggers_defined():
    assert len(STATE_TRIGGERS) == 3

    trigger_names = [(t.from_state, t.to_state, t.command) for t in STATE_TRIGGERS]
    assert (IssueState.READY, IssueState.CLAIMED, "plan") in trigger_names
    assert (IssueState.CLAIMED, IssueState.IN_PROGRESS, "run") in trigger_names
    assert (IssueState.IN_PROGRESS, IssueState.REVIEW, "review") in trigger_names
