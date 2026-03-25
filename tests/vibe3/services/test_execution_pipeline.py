"""Tests for unified execution pipeline contract.

This module tests the execution pipeline which provides a unified interface
for agent execution with artifact persistence and event recording.
"""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from vibe3.models.review_runner import ReviewAgentOptions
from vibe3.services.execution_pipeline import (
    ExecutionPipeline,
    ExecutionRequest,
    ExecutionResult,
)


@pytest.fixture
def mock_git_client():
    """Mock GitClient for testing."""
    client = Mock()
    client.get_current_branch.return_value = "test-branch"
    return client


@pytest.fixture
def mock_agent_execution_service():
    """Mock agent execution service."""
    service = Mock()
    return service


@pytest.fixture
def mock_handoff_service():
    """Mock handoff service."""
    service = Mock()
    service._get_handoff_dir.return_value = Path("/fake/.git/vibe3/handoff/test-branch")
    return service


@pytest.fixture
def pipeline(mock_git_client, mock_handoff_service):
    """Create ExecutionPipeline instance with mocked dependencies."""
    return ExecutionPipeline(
        git_client=mock_git_client, handoff_service=mock_handoff_service
    )


@pytest.fixture
def mock_options():
    """Create mock ReviewAgentOptions."""
    return ReviewAgentOptions(
        agent="executor",
        backend="claude",
        model=None,
    )


class TestExecutionPipelineContract:
    """Test execution pipeline contract."""

    def test_execute_returns_execution_result(self, pipeline, mock_options):
        """Should return ExecutionResult with standard fields."""
        request = ExecutionRequest(
            prompt_content="test prompt",
            options=mock_options,
            artifact_prefix="test",
            event_type="test_event",
            actor="test_actor",
        )

        with patch("vibe3.services.execution_pipeline.execute_agent") as mock_exec:
            mock_exec.return_value = Mock(
                result=Mock(exit_code=0, stdout="output", stderr=""),
                effective_session_id="session-123",
            )

            result = pipeline.execute(request)

            assert isinstance(result, ExecutionResult)
            assert result.success is True
            assert result.session_id == "session-123"

    def test_execute_persists_artifact(
        self, pipeline, mock_options, mock_handoff_service
    ):
        """Should persist artifact after successful execution."""
        request = ExecutionRequest(
            prompt_content="test prompt",
            options=mock_options,
            artifact_prefix="plan",
            event_type="handoff_plan",
            actor="planner",
        )

        with (
            patch("vibe3.services.execution_pipeline.execute_agent") as mock_exec,
            patch(
                "vibe3.services.execution_pipeline.create_handoff_artifact"
            ) as mock_artifact,
        ):

            mock_exec.return_value = Mock(
                result=Mock(exit_code=0, stdout="plan content", stderr=""),
                effective_session_id="session-123",
            )
            mock_artifact.return_value = ("test-branch", Path("plan.md"))

            result = pipeline.execute(request)

            assert result.success is True
            mock_artifact.assert_called_once_with("plan", "plan content")

    def test_execute_records_event(self, pipeline, mock_options, mock_git_client):
        """Should record event after execution."""
        request = ExecutionRequest(
            prompt_content="test prompt",
            options=mock_options,
            artifact_prefix="run",
            event_type="handoff_run",
            actor="executor",
        )

        with (
            patch("vibe3.services.execution_pipeline.execute_agent") as mock_exec,
            patch(
                "vibe3.services.execution_pipeline.create_handoff_artifact"
            ) as mock_artifact,
            patch(
                "vibe3.services.execution_pipeline.persist_handoff_event"
            ) as mock_event,
        ):

            mock_exec.return_value = Mock(
                result=Mock(exit_code=0, stdout="output", stderr=""),
                effective_session_id="session-123",
            )
            mock_artifact.return_value = ("test-branch", Path("run.md"))

            pipeline.execute(request)

            mock_event.assert_called_once()
            call_kwargs = mock_event.call_args[1]
            assert call_kwargs["event_type"] == "handoff_run"
            assert call_kwargs["actor"] == "executor"

    def test_execute_handles_failure_gracefully(self, pipeline, mock_options):
        """Should handle execution failure and still record event."""
        request = ExecutionRequest(
            prompt_content="test prompt",
            options=mock_options,
            artifact_prefix="test",
            event_type="test_event",
            actor="test_actor",
        )

        with (
            patch("vibe3.services.execution_pipeline.execute_agent") as mock_exec,
            patch(
                "vibe3.services.execution_pipeline.persist_handoff_event"
            ) as mock_event,
        ):

            mock_exec.return_value = Mock(
                result=Mock(exit_code=1, stdout="", stderr="error"),
                effective_session_id=None,
            )

            result = pipeline.execute(request)

            assert result.success is False
            mock_event.assert_called_once()


class TestExecutionResultStandardization:
    """Test execution result standardization."""

    def test_result_includes_artifact_path(self, pipeline, mock_options):
        """ExecutionResult should include artifact path when created."""
        request = ExecutionRequest(
            prompt_content="test",
            options=mock_options,
            artifact_prefix="plan",
            event_type="handoff_plan",
            actor="planner",
        )

        with (
            patch("vibe3.services.execution_pipeline.execute_agent") as mock_exec,
            patch(
                "vibe3.services.execution_pipeline.create_handoff_artifact"
            ) as mock_artifact,
        ):

            mock_exec.return_value = Mock(
                result=Mock(exit_code=0, stdout="content", stderr=""),
                effective_session_id="session-123",
            )
            mock_artifact.return_value = ("branch", Path("artifact.md"))

            result = pipeline.execute(request)

            assert result.artifact_path == Path("artifact.md")

    def test_result_includes_session_id(self, pipeline, mock_options):
        """ExecutionResult should include session_id for session continuation."""
        request = ExecutionRequest(
            prompt_content="test",
            options=mock_options,
            artifact_prefix="run",
            event_type="handoff_run",
            actor="executor",
        )

        with (
            patch("vibe3.services.execution_pipeline.execute_agent") as mock_exec,
            patch(
                "vibe3.services.execution_pipeline.create_handoff_artifact"
            ) as mock_artifact,
        ):

            mock_exec.return_value = Mock(
                result=Mock(exit_code=0, stdout="output", stderr=""),
                effective_session_id="session-456",
            )
            mock_artifact.return_value = None  # No artifact created

            result = pipeline.execute(request)

            assert result.session_id == "session-456"
