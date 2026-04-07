"""Tests for review issue state synchronization."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from vibe3.agents.review_agent import ReviewUsecase, _create_minimal_audit_artifact
from vibe3.agents.review_parser import ReviewParserError
from vibe3.models.orchestration import IssueState
from vibe3.models.review import ReviewRequest, ReviewScope


def test_review_success_moves_issue_to_handoff() -> None:
    review_file = Path("/tmp/review-output.md")
    review_file.write_text("VERDICT: PASS\n", encoding="utf-8")
    exec_service = MagicMock()
    exec_service.execute_sync.return_value = MagicMock(
        stdout="VERDICT: PASS",
        handoff_file=str(review_file),
        session_id=None,
    )
    flow_service = MagicMock()
    flow_service.get_flow_status.return_value = MagicMock(audit_ref=str(review_file))
    usecase = ReviewUsecase(
        flow_service=flow_service,
        execution_service_factory=lambda _config: exec_service,
        command_builder=lambda **kwargs: MagicMock(**kwargs),
        review_parser=lambda _stdout: MagicMock(verdict="PASS"),
    )

    with (
        patch("vibe3.agents.review_agent.HandoffService") as mock_handoff,
        patch(
            "vibe3.agents.review_agent.require_authoritative_ref",
            return_value=True,
        ),
        patch("vibe3.agents.review_agent.LabelService") as mock_labels,
    ):
        result = usecase.execute_review(
            ReviewRequest(scope=ReviewScope.for_base("main")),
            dry_run=False,
            instructions=None,
            issue_number=42,
            branch="task/issue-42",
            async_mode=False,
        )

    assert result.verdict == "PASS"
    assert result.handoff_file == str(review_file)
    mock_handoff.return_value.record_audit.assert_called_once_with(
        audit_ref=str(review_file),
        actor="agent:review",
    )
    mock_labels.return_value.confirm_issue_state.assert_called_once_with(
        42,
        to_state=IssueState.HANDOFF,
        actor="agent:review",
    )


def test_review_success_without_handoff_file_creates_minimal_audit_ref() -> None:
    exec_service = MagicMock()
    exec_service.execute_sync.return_value = MagicMock(
        stdout="Summary\n\nVERDICT: PASS",
        handoff_file=None,
        session_id=None,
    )
    flow_service = MagicMock()
    flow_service.get_flow_status.return_value = MagicMock(
        audit_ref="/tmp/generated-audit.md"
    )
    usecase = ReviewUsecase(
        flow_service=flow_service,
        execution_service_factory=lambda _config: exec_service,
        command_builder=lambda **kwargs: MagicMock(**kwargs),
        review_parser=lambda _stdout: MagicMock(verdict="PASS"),
    )

    with (
        patch(
            "vibe3.agents.review_agent._create_minimal_audit_artifact",
            return_value=Path("/tmp/generated-audit.md"),
        ) as mock_create,
        patch("vibe3.agents.review_agent.HandoffService") as mock_handoff,
        patch(
            "vibe3.agents.review_agent.require_authoritative_ref",
            return_value=True,
        ),
        patch("vibe3.agents.review_agent.LabelService") as mock_labels,
    ):
        result = usecase.execute_review(
            ReviewRequest(scope=ReviewScope.for_base("main")),
            dry_run=False,
            instructions=None,
            issue_number=42,
            branch="task/issue-42",
            async_mode=False,
        )

    assert result.verdict == "PASS"
    assert result.handoff_file == "/tmp/generated-audit.md"
    mock_create.assert_called_once_with(
        "Summary\n\nVERDICT: PASS",
        "PASS",
        "task/issue-42",
    )
    mock_handoff.return_value.record_audit.assert_called_once_with(
        audit_ref="/tmp/generated-audit.md",
        actor="agent:review",
    )
    mock_labels.return_value.confirm_issue_state.assert_called_once_with(
        42,
        to_state=IssueState.HANDOFF,
        actor="agent:review",
    )


def test_review_success_uses_shared_authoritative_ref_gate() -> None:
    review_file = Path("/tmp/review-output.md")
    review_file.write_text("VERDICT: PASS\n", encoding="utf-8")
    exec_service = MagicMock()
    exec_service.execute_sync.return_value = MagicMock(
        stdout="VERDICT: PASS",
        handoff_file=str(review_file),
        session_id=None,
    )
    flow_service = MagicMock()
    flow_service.get_flow_status.return_value = MagicMock(audit_ref=str(review_file))
    usecase = ReviewUsecase(
        flow_service=flow_service,
        execution_service_factory=lambda _config: exec_service,
        command_builder=lambda **kwargs: MagicMock(**kwargs),
        review_parser=lambda _stdout: MagicMock(verdict="PASS"),
    )

    with (
        patch("vibe3.agents.review_agent._build_handoff_service") as mock_handoff,
        patch(
            "vibe3.agents.review_agent.require_authoritative_ref",
            return_value=True,
        ) as mock_gate,
        patch("vibe3.agents.review_agent.LabelService") as mock_labels,
    ):
        result = usecase.execute_review(
            ReviewRequest(scope=ReviewScope.for_base("main")),
            dry_run=False,
            instructions=None,
            issue_number=42,
            branch="task/issue-42",
            async_mode=False,
        )

    assert result.verdict == "PASS"
    assert result.handoff_file == str(review_file)
    mock_handoff.return_value.record_audit.assert_called_once()
    mock_gate.assert_called_once()
    mock_labels.return_value.confirm_issue_state.assert_called_once_with(
        42,
        to_state=IssueState.HANDOFF,
        actor="agent:review",
    )


def test_review_missing_audit_ref_blocks_issue() -> None:
    review_file = Path("/tmp/review-output.md")
    review_file.write_text("VERDICT: PASS\n", encoding="utf-8")
    exec_service = MagicMock()
    exec_service.execute_sync.return_value = MagicMock(
        stdout="VERDICT: PASS",
        handoff_file=str(review_file),
        session_id=None,
    )
    flow_service = MagicMock()
    flow_service.get_flow_status.return_value = MagicMock(audit_ref=None)
    usecase = ReviewUsecase(
        flow_service=flow_service,
        execution_service_factory=lambda _config: exec_service,
        command_builder=lambda **kwargs: MagicMock(**kwargs),
        review_parser=lambda _stdout: MagicMock(verdict="PASS"),
    )

    with (
        patch("vibe3.agents.review_agent._build_handoff_service") as mock_handoff,
        patch(
            "vibe3.agents.review_agent.require_authoritative_ref",
            return_value=False,
        ) as mock_gate,
        patch("vibe3.agents.review_agent.LabelService") as mock_labels,
    ):
        result = usecase.execute_review(
            ReviewRequest(scope=ReviewScope.for_base("main")),
            dry_run=False,
            instructions=None,
            issue_number=42,
            branch="task/issue-42",
            async_mode=False,
        )

    assert result.verdict == "ERROR"
    assert result.handoff_file == str(review_file)
    mock_handoff.return_value.record_audit.assert_called_once()
    mock_gate.assert_called_once()
    mock_labels.return_value.confirm_issue_state.assert_not_called()


def test_review_missing_audit_ref_with_flow_but_no_issue_returns_error() -> None:
    review_file = Path("/tmp/review-output.md")
    review_file.write_text("VERDICT: PASS\n", encoding="utf-8")
    exec_service = MagicMock()
    exec_service.execute_sync.return_value = MagicMock(
        stdout="VERDICT: PASS",
        handoff_file=str(review_file),
        session_id=None,
    )
    flow_service = MagicMock()
    flow_service.get_flow_status.return_value = MagicMock(audit_ref=None)
    usecase = ReviewUsecase(
        flow_service=flow_service,
        execution_service_factory=lambda _config: exec_service,
        command_builder=lambda **kwargs: MagicMock(**kwargs),
        review_parser=lambda _stdout: MagicMock(verdict="PASS"),
    )

    with (
        patch("vibe3.agents.review_agent._build_handoff_service") as mock_handoff,
        patch(
            "vibe3.agents.review_agent.require_authoritative_ref",
            return_value=False,
        ) as mock_gate,
        patch("vibe3.agents.review_agent.LabelService") as mock_labels,
    ):
        result = usecase.execute_review(
            ReviewRequest(scope=ReviewScope.for_base("main")),
            dry_run=False,
            instructions=None,
            issue_number=None,
            branch="task/issue-42",
            async_mode=False,
        )

    assert result.verdict == "ERROR"
    assert result.handoff_file == str(review_file)
    mock_handoff.return_value.record_audit.assert_called_once()
    mock_gate.assert_called_once()
    mock_labels.return_value.confirm_issue_state.assert_not_called()


def test_review_without_existing_flow_skips_authoritative_audit_registration() -> None:
    review_file = Path("/tmp/review-output.md")
    review_file.write_text("VERDICT: PASS\n", encoding="utf-8")
    exec_service = MagicMock()
    exec_service.execute_sync.return_value = MagicMock(
        stdout="VERDICT: PASS",
        handoff_file=str(review_file),
        session_id=None,
    )
    flow_service = MagicMock()
    flow_service.get_flow_status.return_value = None
    usecase = ReviewUsecase(
        flow_service=flow_service,
        execution_service_factory=lambda _config: exec_service,
        command_builder=lambda **kwargs: MagicMock(**kwargs),
        review_parser=lambda _stdout: MagicMock(verdict="PASS"),
    )

    with (
        patch("vibe3.agents.review_agent._build_handoff_service") as mock_handoff,
        patch("vibe3.agents.review_agent.require_authoritative_ref") as mock_gate,
        patch("vibe3.agents.review_agent.LabelService") as mock_labels,
    ):
        result = usecase.execute_review(
            ReviewRequest(scope=ReviewScope.for_base("main")),
            dry_run=False,
            instructions=None,
            issue_number=42,
            branch="feature/no-flow",
            async_mode=False,
        )

    assert result.verdict == "PASS"
    assert result.handoff_file == str(review_file)
    mock_handoff.return_value.record_audit.assert_not_called()
    mock_gate.assert_not_called()
    mock_labels.return_value.confirm_issue_state.assert_not_called()


def test_create_minimal_audit_artifact_sanitizes_content(tmp_path) -> None:
    with patch(
        "vibe3.agents.review_agent._build_handoff_service"
    ) as mock_service_builder:
        mock_service_builder.return_value.ensure_handoff_dir.return_value = tmp_path

        result = _create_minimal_audit_artifact(
            "<agent-prompt>secret</agent-prompt>\n\nVERDICT: PASS\nbody",
            "PASS",
            "task/issue-42",
        )

    assert result.exists()
    content = result.read_text(encoding="utf-8")
    assert "secret" not in content
    assert "VERDICT: PASS" in content
    assert "body" in content


def test_review_prompt_can_succeed_without_audit_ref() -> None:
    from vibe3.agents.review_prompt import build_review_prompt_body
    from vibe3.config.settings import VibeConfig

    request = ReviewRequest(scope=ReviewScope.for_base("main"))

    context = build_review_prompt_body(request, VibeConfig.get_defaults())

    assert "VERDICT: PASS | MAJOR | BLOCK" in context
    assert "handoff audit" in context


def test_review_parse_error_fails_issue_and_comments() -> None:
    review_file = Path("/tmp/review-error.md")
    review_file.write_text("bad output", encoding="utf-8")
    exec_service = MagicMock()
    exec_service.execute_sync.return_value = MagicMock(
        stdout="bad output",
        handoff_file=str(review_file),
        session_id=None,
    )
    flow_service = MagicMock()
    flow_service.get_flow_status.return_value = MagicMock(audit_ref=str(review_file))
    usecase = ReviewUsecase(
        flow_service=flow_service,
        execution_service_factory=lambda _config: exec_service,
        command_builder=lambda **kwargs: MagicMock(**kwargs),
        review_parser=lambda _stdout: (_ for _ in ()).throw(
            ReviewParserError("parse failed")
        ),
    )

    with (
        patch("vibe3.agents.review_agent._build_handoff_service") as mock_handoff,
        patch("vibe3.agents.review_agent.GitHubClient") as mock_github,
        patch("vibe3.agents.review_agent.LabelService") as mock_labels,
    ):
        result = usecase.execute_review(
            ReviewRequest(scope=ReviewScope.for_base("main")),
            dry_run=False,
            instructions=None,
            issue_number=42,
            branch="task/issue-42",
            async_mode=False,
        )

    assert result.verdict == "ERROR"
    assert result.handoff_file == str(review_file)
    mock_handoff.return_value.record_audit.assert_called_once_with(
        audit_ref=str(review_file),
        actor="agent:review",
    )
    mock_github.return_value.add_comment.assert_called_once()
    mock_labels.return_value.confirm_issue_state.assert_called_once_with(
        42,
        to_state=IssueState.FAILED,
        actor="agent:review",
        force=True,
    )
