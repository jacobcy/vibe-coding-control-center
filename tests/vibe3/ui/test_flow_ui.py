"""Tests for flow timeline and flow show rendering."""

import tempfile
from pathlib import Path

from vibe3.models.flow import FlowEvent, FlowStatusResponse
from vibe3.ui.flow_ui import render_flow_status, render_flow_timeline


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


def test_render_flow_timeline_prefers_handoff_ref_over_log_path(capsys) -> None:
    state = FlowStatusResponse(
        branch="task/issue-304",
        flow_slug="issue-304",
        flow_status="active",
    )
    artifact_path = (
        "/tmp/.git/vibe3/handoff/task-issue-304-a97faeda/" "run-2026-04-22T14:24:02.md"
    )
    log_path = "/tmp/temp/logs/ses_bad.async.log"
    events = [
        FlowEvent(
            branch="task/issue-304",
            event_type="handoff_report",
            actor="opencode/my-provider/gpt-4o",
            detail="Run completed: run-2026-04-22T14:24:02.md",
            refs={
                "ref": artifact_path,
                "log_path": log_path,
                "session_id": "ses_bad",
            },
        )
    ]

    render_flow_timeline(state, events)

    output = capsys.readouterr().out
    assert artifact_path in output
    assert log_path not in output


def test_render_flow_timeline_distinguishes_handoff_and_system_audit(capsys) -> None:
    state = FlowStatusResponse(
        branch="task/issue-305",
        flow_slug="issue-305",
        flow_status="active",
    )
    events = [
        FlowEvent(
            branch="task/issue-305",
            event_type="handoff_audit",
            actor="claude/claude-sonnet-4-6",
            detail="Recorded audit reference: docs/reports/review.md",
            refs={"ref": "docs/reports/review.md"},
        ),
        FlowEvent(
            branch="task/issue-305",
            event_type="audit_recorded",
            actor="system/reviewer",
            detail="Recorded audit reference: docs/reports/review-auto.md",
            refs={"ref": "docs/reports/review-auto.md"},
        ),
    ]

    render_flow_timeline(state, events)

    output = capsys.readouterr().out
    assert "Audit Handoff" in output
    assert "Audit Auto-Recorded" in output


def test_render_flow_status_shows_absolute_refs_for_humans(capsys) -> None:
    worktree_root = Path(tempfile.mkdtemp(prefix="vibe3-flow-ui-", dir="/tmp"))
    report_file = worktree_root / "docs" / "reports" / "issue-304-report.md"
    report_file.parent.mkdir(parents=True)
    report_file.write_text("report", encoding="utf-8")

    status = FlowStatusResponse(
        branch="task/issue-304",
        flow_slug="issue-304",
        flow_status="active",
        report_ref="docs/reports/issue-304-report.md",
    )

    render_flow_status(status, worktree_root=str(worktree_root))

    output = capsys.readouterr().out
    assert str(worktree_root) in output
    assert "issue-304-report.md" in output
