"""Tests for flow timeline rendering."""

from vibe3.models.flow import FlowEvent, FlowState
from vibe3.ui.flow_ui import render_flow_timeline


def test_render_flow_timeline_shows_run_lifecycle_events(capsys) -> None:
    state = FlowState(
        branch="task/demo",
        flow_slug="demo",
        flow_status="active",
        executor_status="running",
    )
    events = [
        FlowEvent(
            branch="task/demo",
            event_type="run_started",
            actor="executor",
            detail="Run started (status: in_progress)",
        ),
        FlowEvent(
            branch="task/demo",
            event_type="run_completed",
            actor="executor",
            detail="Run completed (status: completed)",
            refs={"ref": "/tmp/run-report.md"},
        ),
    ]

    render_flow_timeline(state, events)

    output = capsys.readouterr().out
    assert "run_started" in output
    assert "in_progress" in output
    assert "run_completed" in output
    assert "/tmp/run-report.md" in output
