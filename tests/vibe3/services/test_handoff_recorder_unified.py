"""Tests for unified handoff recorder."""

from pathlib import Path
from unittest.mock import patch

from vibe3.models.review_runner import AgentOptions
from vibe3.services.handoff_recorder_unified import (
    HandoffRecord,
    parse_modified_files,
    parse_review_verdict,
    record_handoff_unified,
)


def test_parse_modified_files_extracts_paths() -> None:
    content = """# Run\n\n### Modified Files
- src/foo.py: changed
- tests/test_foo.py: added\n\n### Notes\nDone\n"""

    assert parse_modified_files(content) == ["src/foo.py", "tests/test_foo.py"]


def test_parse_review_verdict_supports_block() -> None:
    assert parse_review_verdict("VERDICT: BLOCK") == "BLOCK"


@patch("vibe3.services.handoff_recorder_unified.persist_handoff_event")
@patch("vibe3.services.handoff_recorder_unified.create_handoff_artifact")
def test_record_handoff_unified_for_plan(mock_create, mock_persist) -> None:
    artifact = Path("/tmp/plan-2026-03-26T10:00:00.md")
    mock_create.return_value = ("feature/test", artifact)

    result = record_handoff_unified(
        HandoffRecord(
            kind="plan",
            content="# plan",
            options=AgentOptions(agent="planner"),
            session_id="sess-plan",
        )
    )

    assert result == artifact
    kwargs = mock_persist.call_args.kwargs
    assert kwargs["event_type"] == "handoff_plan"
    assert kwargs["flow_state_updates"]["plan_ref"] == str(artifact)
    assert kwargs["flow_state_updates"]["planner_actor"] == "planner"
    assert kwargs["flow_state_updates"]["planner_session_id"] == "sess-plan"


@patch("vibe3.services.handoff_recorder_unified.persist_handoff_event")
@patch("vibe3.services.handoff_recorder_unified.create_handoff_artifact")
def test_record_handoff_unified_for_run_tracks_modified_files(
    mock_create, mock_persist
) -> None:
    artifact = Path("/tmp/run-2026-03-26T10:00:00.md")
    mock_create.return_value = ("feature/test", artifact)
    content = (
        """### Modified Files\n- src/foo.py: changed\n- tests/test_foo.py: added\n"""
    )

    result = record_handoff_unified(
        HandoffRecord(
            kind="run",
            content=content,
            options=AgentOptions(backend="codex", model="gpt-5.4"),
            session_id="sess-run",
            metadata={"plan_ref": "docs/plans/demo.md"},
        )
    )

    assert result == artifact
    kwargs = mock_persist.call_args.kwargs
    assert kwargs["event_type"] == "handoff_run"
    assert kwargs["refs"]["modified_count"] == "2"
    assert kwargs["refs"]["modified_files"] == "src/foo.py,tests/test_foo.py"
    assert kwargs["refs"]["plan_ref"] == "docs/plans/demo.md"
    assert kwargs["flow_state_updates"]["report_ref"] == str(artifact)
    assert kwargs["flow_state_updates"]["executor_actor"] == "codex/gpt-5.4"
    assert kwargs["flow_state_updates"]["executor_session_id"] == "sess-run"


@patch("vibe3.services.handoff_recorder_unified.persist_handoff_event")
@patch("vibe3.services.handoff_recorder_unified.create_handoff_artifact")
def test_record_handoff_unified_for_review_uses_audit_ref(
    mock_create, mock_persist
) -> None:
    artifact = Path("/tmp/review-2026-03-26T10:00:00.md")
    mock_create.return_value = ("feature/test", artifact)

    result = record_handoff_unified(
        HandoffRecord(
            kind="review",
            content="VERDICT: PASS",
            options=AgentOptions(agent="reviewer"),
            session_id="sess-review",
            metadata={"verdict": "PASS", "comment_count": "3"},
        )
    )

    assert result == artifact
    kwargs = mock_persist.call_args.kwargs
    assert kwargs["event_type"] == "handoff_review"
    assert kwargs["refs"]["verdict"] == "PASS"
    assert kwargs["flow_state_updates"]["audit_ref"] == str(artifact)
    assert kwargs["flow_state_updates"]["reviewer_actor"] == "reviewer"
    assert kwargs["flow_state_updates"]["reviewer_session_id"] == "sess-review"


@patch("vibe3.services.handoff_recorder_unified.persist_handoff_event")
@patch("vibe3.services.handoff_recorder_unified.create_handoff_artifact")
def test_record_handoff_unified_ignores_reserved_metadata_keys(
    mock_create, mock_persist
) -> None:
    artifact = Path("/tmp/run-2026-03-26T10:00:00.md")
    mock_create.return_value = ("feature/test", artifact)

    record_handoff_unified(
        HandoffRecord(
            kind="run",
            content="### Modified Files\n- src/foo.py\n",
            options=AgentOptions(agent="executor"),
            metadata={"backend": "fake-backend", "custom": "ok"},
        )
    )

    refs = mock_persist.call_args.kwargs["refs"]
    assert refs["backend"] == "executor"
    assert refs["custom"] == "ok"
