"""Tests for review issue state synchronization."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from vibe3.agents.review_agent import ReviewUsecase
from vibe3.agents.review_parser import ReviewParserError
from vibe3.domain.events import IssueFailed, ReviewCompleted
from vibe3.models.review import ReviewRequest, ReviewScope


def test_review_success_publishes_review_completed_event() -> None:
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
        patch("vibe3.domain.publisher.publish") as mock_publish,
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
    # Verify ReviewCompleted event published
    mock_publish.assert_called_once()
    event = mock_publish.call_args[0][0]
    assert isinstance(event, ReviewCompleted)
    assert event.issue_number == 42
    assert event.branch == "task/issue-42"
    assert event.verdict == "PASS"


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
        patch("vibe3.agents.review_agent._build_handoff_service") as mock_handoff,
        patch("vibe3.domain.publisher.publish") as mock_publish,
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
    # Verify event published
    mock_publish.assert_called_once()
    event = mock_publish.call_args[0][0]
    assert isinstance(event, ReviewCompleted)
    assert event.issue_number == 42


def test_review_success_uses_event_driven_architecture() -> None:
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
        patch("vibe3.domain.publisher.publish") as mock_publish,
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
    mock_handoff.return_value.record_audit.assert_called_once()
    # verify ReviewCompleted event
    mock_publish.assert_called_once()
    assert isinstance(mock_publish.call_args[0][0], ReviewCompleted)


def test_review_missing_issue_skips_event_publishing() -> None:
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
        patch("vibe3.domain.publisher.publish") as mock_publish,
    ):
        result = usecase.execute_review(
            ReviewRequest(scope=ReviewScope.for_base("main")),
            dry_run=False,
            instructions=None,
            issue_number=None,  # No issue number
            branch="task/issue-42",
            async_mode=False,
        )

    assert result.verdict == "PASS"
    mock_handoff.return_value.record_audit.assert_called_once()
    mock_publish.assert_not_called()


def test_review_without_existing_flow_skips_registration_and_event() -> None:
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
        patch("vibe3.domain.publisher.publish") as mock_publish,
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
    mock_handoff.return_value.record_audit.assert_not_called()
    mock_publish.assert_not_called()


def test_review_parse_error_publishes_issue_failed_event() -> None:
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
        patch("vibe3.domain.publisher.publish") as mock_publish,
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
    mock_handoff.return_value.record_audit.assert_called_once()
    # Verify IssueFailed event published
    mock_publish.assert_called_once()
    event = mock_publish.call_args[0][0]
    assert isinstance(event, IssueFailed)
    assert event.issue_number == 42
    assert "parse failed" in event.reason
