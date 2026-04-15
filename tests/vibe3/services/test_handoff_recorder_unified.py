"""Tests for unified handoff recorder."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from vibe3.models.review_runner import AgentOptions
from vibe3.services.handoff_recorder_unified import (
    HandoffRecord,
    parse_modified_files,
    parse_review_verdict,
    record_handoff_unified,
    sanitize_handoff_content,
)
from vibe3.services.handoff_service import HandoffService


def test_parse_modified_files_extracts_paths() -> None:
    content = """# Run\n\n### Modified Files
- src/foo.py: changed
- tests/test_foo.py: added\n\n### Notes\nDone\n"""

    assert parse_modified_files(content) == ["src/foo.py", "tests/test_foo.py"]


def test_parse_review_verdict_supports_block() -> None:
    assert parse_review_verdict("VERDICT: BLOCK") == "BLOCK"


def test_parse_review_verdict_supports_major() -> None:
    assert parse_review_verdict("VERDICT: MAJOR") == "MAJOR"


def test_sanitize_handoff_content_strips_agent_prompt_block() -> None:
    content = (
        "<agent-prompt>\nsecret prompt\n</agent-prompt>\n\n"
        "/writing-plan\n\nplan body\nSESSION_ID: abc\n"
    )

    result = sanitize_handoff_content(content)

    assert "<agent-prompt>" not in result
    assert "secret prompt" not in result
    assert "/writing-plan" in result
    assert "plan body" in result
    assert "SESSION_ID: abc" in result


def test_create_handoff_artifact_uses_explicit_branch(tmp_path) -> None:
    git_client = MagicMock()
    git_client.get_git_common_dir.return_value = str(tmp_path)

    with patch(
        "vibe3.services.handoff_service.GitClient",
        return_value=git_client,
    ):
        branch, artifact = HandoffService().create_artifact(
            "review",
            "VERDICT: PASS",
            branch="task/issue-42",
        )

    assert branch == "task/issue-42"
    assert artifact.exists()
    assert "task-issue-42" in str(artifact.parent)


@patch("vibe3.services.handoff_service.HandoffService.persist_artifact_event")
@patch("vibe3.services.handoff_service.HandoffService.create_artifact")
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
    # Actor expands agent preset to full backend/model via format_agent_actor
    assert kwargs["flow_state_updates"]["planner_actor"] == "claude/claude-sonnet-4-6"
    # session_id is NOT written to flow_state (registry is source of truth)
    assert "planner_session_id" not in kwargs["flow_state_updates"]
    assert "plan_ref" not in kwargs["flow_state_updates"]
    # Verify log_path is inferred from session_id
    assert "log_path" in kwargs["refs"]
    assert (
        "issue-sess-plan" in kwargs["refs"]["log_path"]
        or "plan.async.log" in kwargs["refs"]["log_path"]
    )


@patch("vibe3.services.handoff_service.HandoffService.persist_artifact_event")
@patch("vibe3.services.handoff_service.HandoffService.create_artifact")
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
    assert kwargs["flow_state_updates"]["executor_actor"] == "codex/gpt-5.4"
    # session_id is NOT written to flow_state (registry is source of truth)
    assert "executor_session_id" not in kwargs["flow_state_updates"]
    assert "report_ref" not in kwargs["flow_state_updates"]


@patch("vibe3.services.handoff_service.HandoffService.persist_artifact_event")
@patch("vibe3.services.handoff_service.HandoffService.create_artifact")
def test_record_handoff_unified_for_review_tracks_verdict_without_audit_ref(
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
    # Actor expands agent preset to full backend/model via format_agent_actor
    assert kwargs["flow_state_updates"]["reviewer_actor"] == "claude/claude-sonnet-4-6"
    # session_id is NOT written to flow_state (registry is source of truth)
    assert "reviewer_session_id" not in kwargs["flow_state_updates"]
    assert "audit_ref" not in kwargs["flow_state_updates"]


@patch("vibe3.services.handoff_service.HandoffService.persist_artifact_event")
@patch("vibe3.services.handoff_service.HandoffService.create_artifact")
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
    # backend is resolved from AgentOptions by resolve_actor_backend_model
    assert refs["backend"] == "opencode"
    assert refs["model"] == "alibaba-coding-plan-cn/glm-5"
    assert refs["custom"] == "ok"


@patch("vibe3.services.handoff_service.HandoffService.persist_artifact_event")
@patch("vibe3.services.handoff_service.HandoffService.create_artifact")
def test_record_handoff_unified_sanitizes_prompt_before_writing(
    mock_create, mock_persist
) -> None:
    artifact = Path("/tmp/plan-2026-03-26T10:00:00.md")
    mock_create.return_value = ("feature/test", artifact)

    record_handoff_unified(
        HandoffRecord(
            kind="plan",
            content=(
                "<agent-prompt>\nsecret prompt\n</agent-prompt>\n\n"
                "/writing-plan\n\nplan body\n"
            ),
            options=AgentOptions(agent="planner"),
            session_id="sess-plan",
        )
    )

    assert "<agent-prompt>" not in mock_create.call_args.args[1]
    assert "secret prompt" not in mock_create.call_args.args[1]
    assert "/writing-plan" in mock_create.call_args.args[1]
    assert "plan body" in mock_create.call_args.args[1]


@patch("vibe3.services.handoff_service.HandoffService.persist_artifact_event")
@patch("vibe3.services.handoff_service.HandoffService.create_artifact")
def test_record_handoff_unified_uses_sanitized_run_content_for_refs(
    mock_create, mock_persist
) -> None:
    artifact = Path("/tmp/run-2026-03-26T10:00:00.md")
    mock_create.return_value = ("feature/test", artifact)

    record_handoff_unified(
        HandoffRecord(
            kind="run",
            content=(
                "<agent-prompt>\n### Modified Files\n"
                "- fake/prompt.py\n</agent-prompt>\n\n"
                "### Modified Files\n- src/real.py: changed\n"
            ),
            options=AgentOptions(agent="executor"),
        )
    )

    refs = mock_persist.call_args.kwargs["refs"]
    assert refs["modified_files"] == "src/real.py"
    assert refs["modified_count"] == "1"


@patch("vibe3.services.handoff_service.HandoffService.persist_artifact_event")
@patch("vibe3.services.handoff_service.HandoffService.create_artifact")
def test_record_handoff_unified_uses_sanitized_review_content_for_verdict(
    mock_create, mock_persist
) -> None:
    artifact = Path("/tmp/review-2026-03-26T10:00:00.md")
    mock_create.return_value = ("feature/test", artifact)

    record_handoff_unified(
        HandoffRecord(
            kind="review",
            content=(
                "<agent-prompt>\nVERDICT: PASS\n</agent-prompt>\n\n" "VERDICT: MAJOR\n"
            ),
            options=AgentOptions(agent="reviewer"),
        )
    )

    refs = mock_persist.call_args.kwargs["refs"]
    assert refs["verdict"] == "MAJOR"


@patch("vibe3.services.handoff_service.HandoffService.persist_artifact_event")
@patch("vibe3.services.handoff_service.HandoffService.create_artifact")
def test_record_handoff_unified_review_prefers_sanitized_content_over_metadata(
    mock_create, mock_persist
) -> None:
    artifact = Path("/tmp/review-2026-03-26T10:00:00.md")
    mock_create.return_value = ("feature/test", artifact)

    record_handoff_unified(
        HandoffRecord(
            kind="review",
            content=(
                "<agent-prompt>\nVERDICT: BLOCK\n</agent-prompt>\n\n" "VERDICT: MAJOR\n"
            ),
            options=AgentOptions(agent="reviewer"),
            metadata={"verdict": "BLOCK"},
        )
    )

    refs = mock_persist.call_args.kwargs["refs"]
    assert refs["verdict"] == "MAJOR"
