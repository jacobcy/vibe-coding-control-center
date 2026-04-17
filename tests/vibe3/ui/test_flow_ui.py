"""Tests for flow timeline rendering."""

from vibe3.models.flow import FlowEvent, FlowStatusResponse
from vibe3.ui.flow_ui import render_flow_timeline


def test_render_flow_timeline_shows_run_lifecycle_events(capsys) -> None:
    state = FlowStatusResponse(
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


def test_render_flow_timeline_shows_verdict_without_duplicate_audit_ref(
    capsys,
) -> None:
    state = FlowStatusResponse(
        branch="task/issue-340",
        flow_slug="issue-340",
        flow_status="active",
    )
    ref_path = "docs/reports/task-issue-340-audit-auto-2026-04-17T12:00:00Z.md"
    events = [
        FlowEvent(
            branch="task/issue-340",
            event_type="handoff_audit",
            actor="claude/claude-sonnet-4-6",
            detail=f"Recorded audit reference: {ref_path}",
            refs={"ref": ref_path, "verdict": "UNKNOWN"},
        )
    ]

    render_flow_timeline(state, events)

    output = capsys.readouterr().out
    assert "verdict: UNKNOWN" in output
    assert output.count(ref_path) == 1
