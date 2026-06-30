"""Tests for issue body models."""

from vibe3.models.issue_body import FlowStateProjection


def test_default_projection():
    """Test default projection is active and empty."""
    proj = FlowStateProjection()
    assert proj.state == "active"
    assert proj.blocked_by == []
    assert proj.blocked_reason is None
    assert proj.is_empty()


def test_blocked_projection():
    """Test blocked state projection."""
    proj = FlowStateProjection(
        state="blocked",
        blocked_by=[123, 456],
        blocked_reason="Waiting for API design",
    )
    assert not proj.is_empty()
    assert proj.state == "blocked"
    assert proj.blocked_by == [123, 456]
