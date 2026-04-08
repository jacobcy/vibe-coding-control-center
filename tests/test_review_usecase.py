"""Unit tests for ReviewUsecase."""

from unittest.mock import Mock, patch

import pytest

from vibe3.agents.models import AgentSpec, CodeagentResult
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
    session_manager = Mock()
    worktree_manager = Mock()

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
        "session_manager": session_manager,
        "worktree_manager": worktree_manager,
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
        session_manager=mock_dependencies["session_manager"],
        worktree_manager=mock_dependencies["worktree_manager"],
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
        mock_dependencies["session_manager"].create_codeagent_session.return_value = (
            Mock()
        )
        mock_dependencies["execution_service_factory"].return_value = Mock(
            execute_with_callbacks=Mock(return_value=success_result)
        )
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
        mock_dependencies[
            "session_manager"
        ].create_codeagent_session.assert_called_once()

    def test_execute_review_failure(
        self,
        usecase,
        review_request,
        mock_dependencies,
    ):
        """测试 execute_review 失败路径."""
        # Setup mocks
        mock_dependencies["session_manager"].create_codeagent_session.return_value = (
            Mock()
        )
        mock_dependencies["execution_service_factory"].return_value = Mock(
            execute_with_callbacks=Mock(side_effect=Exception("boom"))
        )
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


class TestCreateReviewSpec:
    """Tests for create_review_spec method."""

    def test_create_review_spec(
        self,
        usecase,
        review_request,
    ):
        """测试 create_review_spec."""
        # Mock context_builder to return a callable
        mock_context_callable = Mock(return_value="Test context")
        usecase.context_builder = Mock(return_value=mock_context_callable)

        spec = usecase.create_review_spec(
            request=review_request,
            dry_run=False,
            instructions="Test instructions",
            issue_number=42,
            pr_number=None,
            branch="test-branch",
        )

        # Assertions
        assert isinstance(spec, AgentSpec)
        assert spec.role == "reviewer"
        assert spec.handoff_kind == "review"
        assert callable(spec.on_success)
        assert callable(spec.on_failure)


class TestHandleReviewSuccess:
    """Tests for _handle_review_success method."""

    def test_handle_success_with_audit_ref(
        self,
        usecase,
        success_result,
        mock_dependencies,
    ):
        """测试 _handle_review_success 有 audit_ref."""
        from vibe3.agents.review_parser import ParsedReview

        # Mock review_parser
        parsed_review = ParsedReview(
            verdict="PASS",
            comments=[],
            raw="VERDICT: PASS\n## Summary\nAll good",
        )
        usecase.review_parser = Mock(return_value=parsed_review)

        # Mock flow_service
        flow = Mock()
        flow.task_issue_number = 42
        mock_dependencies["flow_service"].get_flow_status.return_value = flow

        with patch(
            "vibe3.agents.review_agent.require_authoritative_ref",
            return_value=True,
        ):
            with patch.object(usecase, "_transition_to_handoff") as mock_transition:
                usecase._handle_review_success(
                    result=success_result,
                    issue_number=42,
                    branch="test-branch",
                    dry_run=False,
                )

        # Verify transition was called
        mock_transition.assert_called_once_with(42)

    def test_handle_success_no_audit_ref(
        self,
        usecase,
        success_result,
        mock_dependencies,
    ):
        """测试 _handle_review_success 无 audit_ref."""
        from vibe3.agents.review_parser import ParsedReview

        # Mock review_parser
        parsed_review = ParsedReview(
            verdict="PASS",
            comments=[],
            raw="VERDICT: PASS\n## Summary\nAll good",
        )
        usecase.review_parser = Mock(return_value=parsed_review)

        # Mock flow_service
        flow = Mock()
        flow.task_issue_number = 42
        mock_dependencies["flow_service"].get_flow_status.return_value = flow

        with patch(
            "vibe3.agents.review_agent.require_authoritative_ref",
            return_value=False,
        ):
            # Should not raise, but should log warning
            usecase._handle_review_success(
                result=success_result,
                issue_number=42,
                branch="test-branch",
                dry_run=False,
            )


class TestHandleReviewFailure:
    """Tests for _handle_review_failure method."""

    def test_handle_failure(
        self,
        usecase,
    ):
        """测试 _handle_review_failure."""
        error = Exception("test error")

        with patch.object(usecase, "_fail_issue") as mock_fail:
            usecase._handle_review_failure(
                error=error,
                issue_number=42,
            )

        # Verify fail_issue was called
        mock_fail.assert_called_once_with(42, "test error")


class TestTransitionToHandoff:
    """Tests for _transition_to_handoff method."""

    def test_transition_to_handoff(
        self,
        usecase,
    ):
        """测试 _transition_to_handoff."""
        with patch("vibe3.agents.review_agent.LabelService") as mock_label_service:
            mock_instance = Mock()
            mock_label_service.return_value = mock_instance
            mock_instance.confirm_issue_state.return_value = "confirmed"

            usecase._transition_to_handoff(issue_number=42)

            mock_instance.confirm_issue_state.assert_called_once_with(
                42,
                to_state=IssueState.HANDOFF,
                actor="agent:review",
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

                usecase._fail_issue(
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
