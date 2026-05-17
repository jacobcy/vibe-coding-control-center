"""Tests for degraded mode manager."""

import pytest

from vibe3.observability.degraded_mode import (
    DegradedModeManager,
    DegradedModeReason,
    get_degraded_manager,
)


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset singleton before and after each test."""
    DegradedModeManager.reset()
    yield
    DegradedModeManager.reset()


def test_enter_degraded_mode():
    """Test entering degraded mode."""
    manager = get_degraded_manager()

    manager.enter_degraded_mode(DegradedModeReason.GITHUB_API_ERROR)

    assert manager.is_degraded() is True
    assert manager.get_reason() == DegradedModeReason.GITHUB_API_ERROR


def test_exit_degraded_mode():
    """Test exiting degraded mode."""
    manager = get_degraded_manager()
    manager.enter_degraded_mode(DegradedModeReason.NETWORK_UNREACHABLE)

    manager.exit_degraded_mode()

    assert manager.is_degraded() is False
    assert manager.get_reason() is None


def test_singleton_instance():
    """Test manager is singleton."""
    manager1 = get_degraded_manager()
    manager2 = get_degraded_manager()

    assert manager1 is manager2
