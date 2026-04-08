"""Unit tests for PlanUsecase."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from vibe3.agents.models import AgentSpec, CodeagentResult
from vibe3.agents.plan_agent import PlanUsecase
from vibe3.models.plan import PlanRequest, PlanScope


@pytest.fixture
def mock_dependencies():
    """Mock dependencies for PlanUsecase."""
    config = Mock()
    flow_service = Mock()
    github_client = Mock()
    spec_ref_service = Mock()
    execution_service = Mock()
    session_manager = Mock()
    worktree_manager = Mock()

    return {
        "config": config,
        "flow_service": flow_service,
        "github_client": github_client,
        "spec_ref_service": spec_ref_service,
        "execution_service": execution_service,
        "session_manager": session_manager,
        "worktree_manager": worktree_manager,
    }


@pytest.fixture
def usecase(mock_dependencies):
    """Create PlanUsecase instance with mocked dependencies."""
    return PlanUsecase(
        config=mock_dependencies["config"],
        flow_service=mock_dependencies["flow_service"],
        github_client=mock_dependencies["github_client"],
        spec_ref_service=mock_dependencies["spec_ref_service"],
        execution_service=mock_dependencies["execution_service"],
        session_manager=mock_dependencies["session_manager"],
        worktree_manager=mock_dependencies["worktree_manager"],
    )


@pytest.fixture
def plan_request():
    """Create a sample PlanRequest."""
    return PlanRequest(
        scope=PlanScope.for_task(42),
        task_guidance="Test task guidance",
    )


@pytest.fixture
def success_result():
    """Create a successful CodeagentResult."""
    return CodeagentResult(
        success=True,
        exit_code=0,
        stdout="Plan created successfully",
        stderr="",
    )


class TestExecutePlan:
    """Tests for execute_plan method."""

    def test_execute_plan_success(
        self,
        usecase,
        plan_request,
        success_result,
        mock_dependencies,
    ):
        """测试 execute_plan 成功路径."""
        # Setup mocks
        mock_dependencies["session_manager"].create_codeagent_session.return_value = (
            Mock()
        )
        mock_dependencies["worktree_manager"].acquire_issue_worktree.return_value = (
            Mock(
                path=Path("/tmp/worktree"),
                is_temporary=False,
            )
        )
        mock_dependencies["execution_service"].execute_with_callbacks.return_value = (
            success_result
        )

        # Mock create_plan_spec to return a spec with no-op callbacks
        spec = AgentSpec(
            role="planner",
            handoff_kind="plan",
            context="Test context",
            task="Test task",
        )
        with patch.object(usecase, "create_plan_spec", return_value=spec):
            result = usecase.execute_plan(
                request=plan_request,
                issue_number=42,
                branch="test-branch",
                async_mode=False,
            )

        # Assertions
        assert result.success
        assert result.exit_code == 0
        mock_dependencies[
            "session_manager"
        ].create_codeagent_session.assert_called_once()
        mock_dependencies[
            "worktree_manager"
        ].acquire_issue_worktree.assert_called_once_with(
            issue_number=42, branch="test-branch"
        )

    def test_execute_plan_failure(
        self,
        usecase,
        plan_request,
        mock_dependencies,
    ):
        """测试 execute_plan 失败路径."""
        # Setup mocks
        mock_dependencies["session_manager"].create_codeagent_session.return_value = (
            Mock()
        )
        mock_dependencies["worktree_manager"].acquire_issue_worktree.return_value = (
            Mock(
                path=Path("/tmp/worktree"),
                is_temporary=False,
            )
        )

        # Mock execute_with_callbacks to raise exception
        mock_dependencies["execution_service"].execute_with_callbacks.side_effect = (
            Exception("boom")
        )

        # Mock create_plan_spec to return a spec with no-op callbacks
        spec = AgentSpec(
            role="planner",
            handoff_kind="plan",
            context="Test context",
            task="Test task",
        )
        with patch.object(usecase, "create_plan_spec", return_value=spec):
            with pytest.raises(Exception, match="boom"):
                usecase.execute_plan(
                    request=plan_request,
                    issue_number=42,
                    branch="test-branch",
                    async_mode=False,
                )


class TestHandlePlanSuccess:
    """Tests for _handle_plan_success method."""

    def test_handle_success_with_ref(
        self,
        usecase,
        success_result,
        mock_dependencies,
    ):
        """测试 _handle_plan_success 有 plan_ref."""
        # Mock _require_plan_ref to return True
        with patch.object(usecase, "_require_plan_ref", return_value=True):
            with patch.object(usecase, "_transition_to_handoff") as mock_transition:
                usecase._handle_plan_success(
                    result=success_result,
                    issue_number=42,
                    branch="test-branch",
                )

        # Verify transition_to_handoff was called
        mock_transition.assert_called_once_with(42)

    def test_handle_success_no_ref(
        self,
        usecase,
        success_result,
        mock_dependencies,
    ):
        """测试 _handle_plan_success 无 plan_ref."""
        # Mock _require_plan_ref to return False
        with patch.object(usecase, "_require_plan_ref", return_value=False):
            with patch.object(usecase, "_block_issue") as mock_block:
                usecase._handle_plan_success(
                    result=success_result,
                    issue_number=42,
                    branch="test-branch",
                )

        # Verify block_issue was called
        mock_block.assert_called_once_with(
            issue_number=42,
            reason="Missing authoritative plan_ref",
        )


class TestHandlePlanFailure:
    """Tests for _handle_plan_failure method."""

    def test_handle_failure(
        self,
        usecase,
        mock_dependencies,
    ):
        """测试 _handle_plan_failure."""
        error = Exception("test error")

        with patch.object(usecase, "_fail_issue") as mock_fail:
            usecase._handle_plan_failure(
                error=error,
                issue_number=42,
            )

        # Verify fail_issue was called
        mock_fail.assert_called_once_with(
            issue_number=42,
            reason="test error",
        )


class TestCreatePlanSpec:
    """Tests for create_plan_spec method."""

    def test_create_plan_spec(
        self,
        usecase,
        plan_request,
    ):
        """测试 create_plan_spec."""
        # Mock make_plan_context_builder to avoid dependency on config
        with patch("vibe3.agents.plan_agent.make_plan_context_builder") as mock_builder:
            # Create a mock context_builder that returns a test string
            mock_context_builder = Mock(return_value="Test context")
            mock_builder.return_value = mock_context_builder

            spec = usecase.create_plan_spec(
                request=plan_request,
                issue_number=42,
                branch="test-branch",
            )

        # Assertions
        assert isinstance(spec, AgentSpec)
        assert spec.role == "planner"
        assert spec.handoff_kind == "plan"
        assert spec.task == "Test task guidance"
        assert spec.context == "Test context"
        assert callable(spec.on_success)
        assert callable(spec.on_failure)


class TestRequirePlanRef:
    """Tests for _require_plan_ref method."""

    def test_require_plan_ref_exists(
        self,
        usecase,
        mock_dependencies,
    ):
        """测试 _require_plan_ref 存在的情况."""
        # Mock require_authoritative_ref to return True
        with patch(
            "vibe3.agents.plan_agent.require_authoritative_ref",
            return_value=True,
        ):
            result = usecase._require_plan_ref(
                issue_number=42,
                branch="test-branch",
            )

        assert result is True

    def test_require_plan_ref_missing(
        self,
        usecase,
        mock_dependencies,
    ):
        """测试 _require_plan_ref 缺失的情况."""
        # Mock require_authoritative_ref to return False
        with patch(
            "vibe3.agents.plan_agent.require_authoritative_ref",
            return_value=False,
        ):
            result = usecase._require_plan_ref(
                issue_number=42,
                branch="test-branch",
            )

        assert result is False


class TestBlockIssue:
    """Tests for _block_issue method."""

    def test_block_issue(
        self,
        usecase,
    ):
        """测试 _block_issue."""
        with patch("vibe3.agents.plan_agent.block_planner_noop_issue") as mock_block:
            usecase._block_issue(
                issue_number=42,
                reason="Test reason",
            )

        mock_block.assert_called_once_with(
            issue_number=42,
            reason="Test reason",
            actor="agent:plan",
        )


class TestTransitionToHandoff:
    """Tests for _transition_to_handoff method."""

    def test_transition_to_handoff(
        self,
        usecase,
    ):
        """测试 _transition_to_handoff."""
        with patch("vibe3.agents.plan_agent.confirm_plan_handoff") as mock_confirm:
            usecase._transition_to_handoff(issue_number=42)

        mock_confirm.assert_called_once_with(
            issue_number=42,
            actor="agent:plan",
        )


class TestFailIssue:
    """Tests for _fail_issue method."""

    def test_fail_issue(
        self,
        usecase,
    ):
        """测试 _fail_issue."""
        with patch("vibe3.agents.plan_agent.fail_planner_issue") as mock_fail:
            usecase._fail_issue(
                issue_number=42,
                reason="Test reason",
            )

        mock_fail.assert_called_once_with(
            issue_number=42,
            reason="Test reason",
            actor="agent:plan",
        )
