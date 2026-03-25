"""Tests for HandoffUseCase orchestration service.

This module tests the handoff usecase service which handles:
- Reference recording
- Artifact writing
- Event appending
- Error paths
"""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from vibe3.services.handoff_usecase import HandoffUseCase


@pytest.fixture
def mock_git_client():
    """Mock GitClient for testing."""
    client = Mock()
    client.get_current_branch.return_value = "test-branch"
    client.get_git_common_dir.return_value = Path("/fake/.git")
    return client


@pytest.fixture
def mock_handoff_service():
    """Mock HandoffService for testing."""
    service = Mock()
    service._get_handoff_dir.return_value = Path("/fake/.git/vibe3/handoff/test-branch")
    return service


@pytest.fixture
def handoff_usecase(mock_git_client, mock_handoff_service):
    """Create HandoffUseCase instance with mocked dependencies."""
    return HandoffUseCase(
        git_client=mock_git_client, handoff_service=mock_handoff_service
    )


class TestHandoffUseCaseReferenceRecording:
    """Test reference recording behavior."""

    def test_record_plan_reference(self, handoff_usecase):
        """Should record plan reference correctly."""
        with patch.object(
            handoff_usecase.handoff_service, "record_plan"
        ) as mock_record:
            handoff_usecase.record_reference(
                ref_type="plan", ref_value="plans/2026-03-25-test.md", actor="planner"
            )

            mock_record.assert_called_once_with(
                "plans/2026-03-25-test.md", None, None, "planner"
            )

    def test_record_run_reference(self, handoff_usecase):
        """Should record run reference correctly."""
        with patch.object(
            handoff_usecase.handoff_service, "record_report"
        ) as mock_record:
            handoff_usecase.record_reference(
                ref_type="report", ref_value="run-2026-03-25.md", actor="executor"
            )

            mock_record.assert_called_once_with(
                "run-2026-03-25.md", None, None, "executor"
            )


class TestHandoffUseCaseArtifactWriting:
    """Test artifact writing behavior."""

    def test_create_artifact_success(self, handoff_usecase):
        """Should create artifact successfully."""
        content = "Test artifact content"

        with patch(
            "vibe3.services.handoff_usecase.create_handoff_artifact"
        ) as mock_create:
            mock_create.return_value = ("test-branch", Path("artifact.md"))

            result = handoff_usecase.create_artifact("test", content)

            assert result is not None
            mock_create.assert_called_once_with("test", content)

    def test_create_artifact_failure_returns_none(self, handoff_usecase):
        """Should return None when artifact creation fails."""
        content = "Test content"

        with patch(
            "vibe3.services.handoff_usecase.create_handoff_artifact"
        ) as mock_create:
            mock_create.return_value = None

            result = handoff_usecase.create_artifact("test", content)

            assert result is None


class TestHandoffUseCaseEventAppending:
    """Test event appending behavior."""

    def test_append_event_success(self, handoff_usecase):
        """Should append event successfully."""
        with patch(
            "vibe3.services.handoff_usecase.persist_handoff_event"
        ) as mock_persist:
            handoff_usecase.append_event(
                event_type="handoff_plan", actor="planner", detail="Plan created"
            )

            mock_persist.assert_called_once()

    def test_append_event_with_refs(self, handoff_usecase):
        """Should append event with references."""
        with patch(
            "vibe3.services.handoff_usecase.persist_handoff_event"
        ) as mock_persist:
            handoff_usecase.append_event(
                event_type="handoff_run",
                actor="executor",
                detail="Run completed",
                refs={"plan_ref": "plans/test.md", "run_ref": "runs/test.md"},
            )

            mock_persist.assert_called_once()
            call_kwargs = mock_persist.call_args[1]
            assert "refs" in call_kwargs
            assert call_kwargs["refs"]["plan_ref"] == "plans/test.md"


class TestHandoffUseCaseErrorPaths:
    """Test error handling paths."""

    def test_create_artifact_handles_exception(self, handoff_usecase):
        """Should handle exceptions during artifact creation."""
        with patch(
            "vibe3.services.handoff_usecase.create_handoff_artifact"
        ) as mock_create:
            mock_create.side_effect = Exception("Write failed")

            result = handoff_usecase.create_artifact("test", "content")

            assert result is None

    def test_append_event_handles_exception(self, handoff_usecase):
        """Should handle exceptions during event append."""
        with patch(
            "vibe3.services.handoff_usecase.persist_handoff_event"
        ) as mock_persist:
            mock_persist.side_effect = Exception("Database error")

            # Should not raise exception
            handoff_usecase.append_event(event_type="test", actor="test", detail="test")
