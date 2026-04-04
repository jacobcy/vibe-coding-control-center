"""Tests for review issue state synchronization."""

from unittest.mock import MagicMock, patch

from vibe3.agents.review_agent import ReviewUsecase
from vibe3.agents.review_parser import ReviewParserError
from vibe3.models.orchestration import IssueState
from vibe3.models.review import ReviewRequest, ReviewScope


def test_review_success_moves_issue_to_handoff() -> None:
    exec_service = MagicMock()
    exec_service.execute_sync.return_value = MagicMock(
        stdout="VERDICT: PASS",
        handoff_file=None,
        session_id=None,
    )
    usecase = ReviewUsecase(
        execution_service_factory=lambda _config: exec_service,
        command_builder=lambda **kwargs: MagicMock(**kwargs),
        review_parser=lambda _stdout: MagicMock(verdict="PASS"),
    )

    with patch("vibe3.agents.review_agent.LabelService") as mock_labels:
        result = usecase.execute_review(
            ReviewRequest(scope=ReviewScope.for_base("main")),
            dry_run=False,
            instructions=None,
            issue_number=42,
            branch="task/issue-42",
            async_mode=False,
        )

    assert result.verdict == "PASS"
    mock_labels.return_value.confirm_issue_state.assert_called_once_with(
        42,
        to_state=IssueState.HANDOFF,
        actor="agent:review",
    )


def test_review_parse_error_fails_issue_and_comments() -> None:
    exec_service = MagicMock()
    exec_service.execute_sync.return_value = MagicMock(
        stdout="bad output",
        handoff_file=None,
        session_id=None,
    )
    usecase = ReviewUsecase(
        execution_service_factory=lambda _config: exec_service,
        command_builder=lambda **kwargs: MagicMock(**kwargs),
        review_parser=lambda _stdout: (_ for _ in ()).throw(
            ReviewParserError("parse failed")
        ),
    )

    with (
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
    mock_github.return_value.add_comment.assert_called_once()
    mock_labels.return_value.confirm_issue_state.assert_called_once_with(
        42,
        to_state=IssueState.FAILED,
        actor="agent:review",
        force=True,
    )
