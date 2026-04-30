"""Tests for flow_ui_timeline filtering logic."""

from vibe3.models.flow import FlowEvent
from vibe3.ui.flow_ui_timeline import _filter_passive_if_active_exists


def test_filter_passive_if_active_exists_removes_recorded():
    """Test that passive recorded events are removed when active events exist."""
    events = [
        FlowEvent(
            event_type="handoff_report",
            created_at="2024-01-01T00:00:00Z",
            actor="agent",
            branch="test-branch",
        ),
        FlowEvent(
            event_type="report_recorded",
            created_at="2024-01-01T00:01:00Z",
            actor="agent",
            branch="test-branch",
        ),
    ]
    result = _filter_passive_if_active_exists(events)
    assert [e.event_type for e in result] == ["handoff_report"]


def test_filter_passive_if_active_exists_keeps_recorded_when_no_active():
    """Test that passive recorded events are kept when no active events exist."""
    events = [
        FlowEvent(
            event_type="report_recorded",
            created_at="2024-01-01T00:00:00Z",
            actor="agent",
            branch="test-branch",
        )
    ]
    result = _filter_passive_if_active_exists(events)
    assert [e.event_type for e in result] == ["report_recorded"]


def test_filter_legacy_handoff_run_suppresses_report_recorded():
    """Test that legacy handoff_run suppresses report_recorded."""
    events = [
        FlowEvent(
            event_type="handoff_run",
            created_at="2024-01-01T00:00:00Z",
            actor="agent",
            branch="test-branch",
        ),
        FlowEvent(
            event_type="report_recorded",
            created_at="2024-01-01T00:01:00Z",
            actor="agent",
            branch="test-branch",
        ),
    ]
    result = _filter_passive_if_active_exists(events)
    assert [e.event_type for e in result] == ["handoff_run"]


def test_filter_keeps_unrelated_events():
    """Test that unrelated events are not filtered."""
    events = [
        FlowEvent(
            event_type="flow_created",
            created_at="2024-01-01T00:00:00Z",
            actor="agent",
            branch="test-branch",
        ),
        FlowEvent(
            event_type="task_bound",
            created_at="2024-01-01T00:01:00Z",
            actor="agent",
            branch="test-branch",
        ),
    ]
    result = _filter_passive_if_active_exists(events)
    assert len(result) == 2


def test_filter_handles_multiple_kinds():
    """Test filtering with multiple active/passive pairs."""
    events = [
        FlowEvent(
            event_type="handoff_plan",
            created_at="2024-01-01T00:00:00Z",
            actor="agent",
            branch="test-branch",
        ),
        FlowEvent(
            event_type="plan_recorded",
            created_at="2024-01-01T00:01:00Z",
            actor="agent",
            branch="test-branch",
        ),
        FlowEvent(
            event_type="handoff_audit",
            created_at="2024-01-01T00:02:00Z",
            actor="agent",
            branch="test-branch",
        ),
        FlowEvent(
            event_type="audit_recorded",
            created_at="2024-01-01T00:03:00Z",
            actor="agent",
            branch="test-branch",
        ),
    ]
    result = _filter_passive_if_active_exists(events)
    assert set(e.event_type for e in result) == {"handoff_plan", "handoff_audit"}


def test_filter_empty_list():
    """Test that empty list returns empty list."""
    result = _filter_passive_if_active_exists([])
    assert result == []
