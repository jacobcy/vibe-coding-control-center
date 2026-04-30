"""Tests for async_execution config field."""

from vibe3.models.orchestra_config import OrchestraConfig


def test_async_execution_default_is_true() -> None:
    """Default value of async_execution should be True."""
    config = OrchestraConfig()
    assert config.async_execution is True


def test_async_execution_can_be_set_to_false() -> None:
    """async_execution can be explicitly set to False."""
    config = OrchestraConfig(async_execution=False)
    assert config.async_execution is False


def test_async_execution_can_be_set_via_kwargs() -> None:
    """async_execution can be set via kwargs (simulating YAML/settings loading)."""
    config = OrchestraConfig(**{"async_execution": False})
    assert config.async_execution is False
