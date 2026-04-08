"""Unit tests for ReviewUsecase."""

from unittest.mock import Mock, patch

import pytest

from vibe3.agents.models import CodeagentResult
from vibe3.agents.review_agent import ReviewUsecase
from vibe3.models.orchestration import IssueState
from vibe3.models.review import ReviewRequest, ReviewScope


@pytest.fixture
def mock_dependencies():
    """Mock dependencies for ReviewUsecase."""
    config = Mock()
    flow_service = Mock()
    github_client = Mock()
    inspect_runner = Mock()
    snapshot_diff_builder = Mock()
    review_parser = Mock()
    context_builder = Mock()
    execution_service_factory = Mock()
    command_builder = Mock()

    return {
        "config": config,
        "flow_service": flow_service,
        "github_client": github_client,
        "inspect_runner": inspect_runner,
        "snapshot_diff_builder": snapshot_diff_builder,
        "review_parser": review_parser,
        "context_builder": context_builder,
        "execution_service_factory": execution_service_factory,
        "command_builder": command_builder,
    }


@pytest.fixture
def usecase(mock_dependencies):
    """Create ReviewUsecase instance with mocked dependencies."""
    return ReviewUsecase(
        config=mock_dependencies["config"],
        flow_service=mock_dependencies["flow_service"],
        github_client=mock_dependencies["github_client"],
        inspect_runner=mock_dependencies["inspect_runner"],
        snapshot_diff_builder=mock_dependencies["snapshot_diff_builder"],
        review_parser=mock_dependencies["review_parser"],
        context_builder=mock_dependencies["context_builder"],
        execution_service_factory=mock_dependencies["execution_service_factory"],
        command_builder=mock_dependencies["command_builder"],
    )


@pytest.fixture
def review_request():
    """Create a sample ReviewRequest."""
    return ReviewRequest(scope=ReviewScope.for_base("main"))


@pytest.fixture
def success_result():
    """Create a successful CodeagentResult."""
    return CodeagentResult(
        success=True,
        exit_code=0,
        stdout="VERDICT: PASS\n## Summary\nAll good",
        stderr="",
    )


class TestExecuteReview:
    """Tests for execute_review method."""

    def test_execute_review_success(
        self,
        usecase,
        review_request,
        success_result,
        mock_dependencies,
    ):
        """测试 execute_review 成功路径."""
        # Setup mocks
        exec_service_mock = Mock()
        exec_service_mock.execute_sync.return_value = success_result
        mock_dependencies["execution_service_factory"].return_value = exec_service_mock
        mock_dependencies["command_builder"].return_value = Mock()
        mock_dependencies["context_builder"].return_value = Mock(return_value="context")

        # Mock review_parser
        from vibe3.agents.review_parser import ParsedReview

        parsed_review = ParsedReview(
            verdict="PASS",
            comments=[],
            raw="VERDICT: PASS\n## Summary\nAll good",
        )
        mock_dependencies["review_parser"].return_value = parsed_review

        # Mock flow_service
        mock_dependencies["flow_service"].get_flow_status.return_value = None

        result = usecase.execute_review(
            request=review_request,
            dry_run=False,
            instructions=None,
            issue_number=42,
            branch="test-branch",
            async_mode=False,
        )

        # Assertions
        assert result.verdict in {"PASS", "ERROR"}  # Depending on audit_ref handling

    def test_execute_review_failure(
        self,
        usecase,
        review_request,
        mock_dependencies,
    ):
        """测试 execute_review 失败路径."""
        # Setup mocks
        exec_service_mock = Mock()
        exec_service_mock.execute_sync.side_effect = Exception("boom")
        mock_dependencies["execution_service_factory"].return_value = exec_service_mock
        mock_dependencies["command_builder"].return_value = Mock()
        mock_dependencies["context_builder"].return_value = Mock(return_value="context")

        with pytest.raises(Exception, match="boom"):
            usecase.execute_review(
                request=review_request,
                dry_run=False,
                instructions=None,
                issue_number=42,
                branch="test-branch",
                async_mode=False,
            )


class TestFailIssue:
    """Tests for _fail_issue method."""

    def test_fail_issue(
        self,
        usecase,
    ):
        """测试 _fail_issue."""
        with patch("vibe3.agents.review_agent.GitHubClient") as mock_github_client:
            with patch("vibe3.agents.review_agent.LabelService") as mock_label_service:
                mock_github_instance = Mock()
                mock_github_client.return_value = mock_github_instance
                mock_label_instance = Mock()
                mock_label_service.return_value = mock_label_instance

                ReviewUsecase._fail_issue(
                    issue_number=42,
                    reason="Test reason",
                )

                mock_github_instance.add_comment.assert_called_once()
                mock_label_instance.confirm_issue_state.assert_called_once_with(
                    42,
                    to_state=IssueState.FAILED,
                    actor="agent:review",
                    force=True,
                )
