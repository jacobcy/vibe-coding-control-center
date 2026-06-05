"""Tests for orchestra_config module."""

from vibe3.models.orchestra_config import QueueRecollectConfig


def test_queue_recollect_config_defaults():
    """Test QueueRecollectConfig has correct defaults."""
    config = QueueRecollectConfig()
    assert config.enabled is True
    assert config.interval_ticks == 10
