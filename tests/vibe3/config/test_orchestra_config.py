"""Tests for orchestra_config module."""

from vibe3.models.orchestra_config import OrchestraConfig, QueueRecollectConfig


def test_queue_recollect_config_defaults():
    """Test QueueRecollectConfig has correct defaults."""
    config = QueueRecollectConfig()
    assert config.enabled is True
    assert config.interval_ticks == 10


def test_orchestra_config_has_queue_recollect():
    """Test OrchestraConfig has queue_recollect field with defaults."""
    config = OrchestraConfig()
    assert hasattr(config, "queue_recollect")
    assert isinstance(config.queue_recollect, QueueRecollectConfig)
    assert config.queue_recollect.enabled is True
    assert config.queue_recollect.interval_ticks == 10
