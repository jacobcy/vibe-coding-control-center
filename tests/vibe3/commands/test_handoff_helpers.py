"""Tests for handoff helper functions."""

from datetime import datetime, timedelta, timezone

import pytest

from vibe3.commands.handoff_read import _format_relative_time
from vibe3.commands.handoff_render import _render_handoff_events
from vibe3.models.flow import FlowEvent


@pytest.mark.parametrize(
    "seconds_offset,expected_output",
    [
        pytest.param(0, "just now", id="0_seconds"),
        pytest.param(30, "just now", id="30_seconds"),
        pytest.param(59, "just now", id="59_seconds"),
        pytest.param(60, "1 minute ago", id="60_seconds"),
        pytest.param(61, "1 minute ago", id="61_seconds"),
        pytest.param(120, "2 minutes ago", id="120_seconds"),
        pytest.param(3599, "59 minutes ago", id="3599_seconds"),
        pytest.param(3600, "1 hour ago", id="3600_seconds"),
        pytest.param(7200, "2 hours ago", id="7200_seconds"),
        pytest.param(86399, "23 hours ago", id="86399_seconds"),
        pytest.param(86400, "1 day ago", id="86400_seconds"),
        pytest.param(172800, "2 days ago", id="172800_seconds"),
        pytest.param(2591999, "29 days ago", id="2591999_seconds"),
        pytest.param(2592000, "1 month ago", id="2592000_seconds"),
        pytest.param(5184000, "2 months ago", id="5184000_seconds"),
    ],
)
def test_format_relative_time_boundary_values(seconds_offset, expected_output):
    """Test _format_relative_time at key boundaries.

    Verifies correct pluralization and unit transitions at:
    - 59s → 60s: just now → 1 minute ago
    - 59m → 60m: 59 minutes ago → 1 hour ago
    - 23h → 24h: 23 hours ago → 1 day ago
    - 29d → 30d: 29 days ago → 1 month ago
    """
    # Use fixed clock to avoid scheduler delay flakiness
    # Pass explicit now parameter instead of relying on real clock
    fixed_now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    timestamp = fixed_now - timedelta(seconds=seconds_offset)
    result = _format_relative_time(timestamp, now=fixed_now)
    assert result == expected_output


def test_format_relative_time_assumes_utc_for_naive_datetime():
    """Test that naive datetime (no timezone) is assumed to be UTC."""
    # Use fixed clock to avoid scheduler delay flakiness
    # Pass explicit now parameter instead of relying on real clock
    # If the test reads the real clock twice (once here, once in the function),
    # and the scheduler delays between calls, "5 minutes ago" could become
    # "6 minutes ago" and fail the assertion.
    fixed_now = datetime(2026, 1, 1, 12, 5, 0, tzinfo=timezone.utc)
    naive_timestamp = (fixed_now - timedelta(minutes=5)).replace(tzinfo=None)
    result = _format_relative_time(naive_timestamp, now=fixed_now)
    # Should treat it as UTC and return "5 minutes ago"
    assert result == "5 minutes ago"


def test_render_handoff_events_sanitizes_absolute_ref_in_detail(capsys) -> None:
    worktree_root = "/workspace/vibe-center/.worktrees/task/issue-417"
    abs_ref = (
        "/workspace/vibe-center/.worktrees/task/issue-417/"
        "docs/reports/task-issue-417-audit-auto-2026-04-21T01:41:01Z.md"
    )
    event = FlowEvent(
        branch="task/issue-417",
        event_type="handoff_audit",
        actor="claude/claude-sonnet-4-6",
        detail=f"Recorded audit reference: {abs_ref}",
        refs={"audit_ref": abs_ref, "verdict": "UNKNOWN"},
        created_at="2026-04-21T09:41:02",
    )

    _render_handoff_events([event], worktree_root=worktree_root)

    output = capsys.readouterr().out
    assert abs_ref not in output
    assert "docs/reports/task-issue-417-audit-auto-2026-04-21T01:41:01Z.md" in output


def test_render_handoff_events_shows_success_event_names(capsys) -> None:
    """Verify that successful handoff events render correctly."""
    event = FlowEvent(
        branch="task/issue-417",
        event_type="handoff_plan",
        actor="codex/gpt-4o",
        detail="Plan artifact recorded",
        refs={"plan_ref": "docs/plans/example.md"},
        created_at="2026-04-21T10:00:00",
    )

    _render_handoff_events([event])

    output = capsys.readouterr().out
    # Should show "Plan Handoff" (display name for handoff_plan)
    assert "Plan Handoff" in output


def test_render_handoff_events_shows_files_without_ref_alias(capsys) -> None:
    """File refs are display paths, not database ref aliases."""
    event = FlowEvent(
        branch="task/issue-417",
        event_type="handoff_plan",
        actor="codex/gpt-5.4",
        detail="Plan artifact recorded",
        refs={"files": ["src/vibe3/example.py"]},
        created_at="2026-04-21T10:00:00",
    )

    _render_handoff_events([event], branch="task/issue-417")

    output = capsys.readouterr().out
    assert "src/vibe3/example.py" in output
    assert "vibe3 handoff show" not in output
