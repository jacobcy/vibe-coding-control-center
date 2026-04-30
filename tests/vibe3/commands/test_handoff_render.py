from vibe3.commands.handoff_render import _render_handoff_events
from vibe3.models.flow import FlowEvent


def test_render_handoff_events_sanitizes_absolute_ref_in_detail(capsys) -> None:
    worktree_root = "/Users/jacobcy/src/vibe-center/main/.worktrees/task/issue-417"
    abs_ref = (
        "/Users/jacobcy/src/vibe-center/main/.worktrees/task/issue-417/"
        "docs/reports/task-issue-417-audit-auto-2026-04-21T01:41:01Z.md"
    )
    event = FlowEvent(
        branch="task/issue-417",
        event_type="handoff_audit",
        actor="claude/claude-sonnet-4-6",
        detail=f"Recorded audit reference: {abs_ref}",
        refs={"ref": abs_ref, "verdict": "UNKNOWN"},
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
        refs={"ref": "docs/plans/example.md"},
        created_at="2026-04-21T10:00:00",
    )

    _render_handoff_events([event])

    output = capsys.readouterr().out
    # Should show "Plan Handoff" (display name for handoff_plan)
    assert "Plan Handoff" in output
