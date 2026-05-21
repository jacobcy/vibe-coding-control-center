"""Test that qualify_gate uses service layer for blocked state changes."""

from unittest.mock import MagicMock, patch

from vibe3.domain.qualify_gate import QualifyGateService
from vibe3.models.orchestration import IssueState


class TestAlignBlockedStateUsesServiceLayer:
    """Test _align_blocked_state routes through FlowService.block_flow()."""

    def test_calls_block_flow_with_reason_and_blocked_by(self):
        """Should call FlowService.block_flow() with correct parameters."""
        service = QualifyGateService.__new__(QualifyGateService)
        service._store = MagicMock()
        service._convention = MagicMock()
        service.config = MagicMock()
        service.config.repo = "test/repo"

        truth = MagicMock(
            blocked_reason="dependency issue",
            blocked_by_issue=200,
        )

        with patch("vibe3.domain.qualify_gate.FlowService") as mock_flow_service:
            mock_fs_instance = MagicMock()
            mock_flow_service.return_value = mock_fs_instance

            service._align_blocked_state(
                issue_number=100,
                branch="test-branch",
                truth=truth,
                labels=["state/blocked"],
                flow_state={"flow_status": "active"},
            )

            # Verify block_flow was called with correct parameters
            mock_flow_service.assert_called_once_with(store=service._store)
            mock_fs_instance.block_flow.assert_called_once_with(
                branch="test-branch",
                reason="dependency issue",
                blocked_by_issue=200,
                actor="orchestra:qualify",
            )

    def test_does_not_call_store_directly(self):
        """Should NOT call _store.update_flow_state directly."""
        service = QualifyGateService.__new__(QualifyGateService)
        service._store = MagicMock()
        service._convention = MagicMock()
        service.config = MagicMock()
        service.config.repo = "test/repo"

        truth = MagicMock(
            blocked_reason="test reason",
            blocked_by_issue=None,
        )

        with patch("vibe3.domain.qualify_gate.FlowService"):
            service._align_blocked_state(
                issue_number=100,
                branch="test-branch",
                truth=truth,
                labels=["state/blocked"],
                flow_state=None,
            )

            # Should NOT call store directly
            service._store.update_flow_state.assert_not_called()


class TestAutoResumeBlockedUsesServiceLayer:
    """Test _auto_resume_blocked routes through resume_issue()."""

    def test_calls_resume_issue_with_correct_params(self):
        """Should call resume_issue() with issue_number and target state."""
        service = QualifyGateService.__new__(QualifyGateService)
        service._store = MagicMock()
        service._convention = MagicMock()
        service.config = MagicMock()
        service.config.repo = "test/repo"

        with patch("vibe3.domain.qualify_gate.resume_issue") as mock_resume:
            result = service._auto_resume_blocked(
                issue_number=100,
                branch="test-branch",
                labels=["state/ready"],
                flow_state={
                    "flow_status": "blocked",
                    "branch": "test-branch",
                    "flow_slug": "test-slug",
                },
            )

            # Verify resume_issue was called
            mock_resume.assert_called_once()
            call_kwargs = mock_resume.call_args[1]
            assert call_kwargs["issue_number"] == 100
            assert call_kwargs["reason"] == "Auto-resume: body truth not blocked"
            assert call_kwargs["from_state"] == "blocked"
            assert call_kwargs["actor"] == "orchestra:qualify"
            assert call_kwargs["repo"] == "test/repo"

            # Should return target state
            assert result in [IssueState.READY, IssueState.CLAIMED]

    def test_does_not_call_store_directly(self):
        """Should NOT call _store.update_flow_state directly."""
        service = QualifyGateService.__new__(QualifyGateService)
        service._store = MagicMock()
        service._convention = MagicMock()
        service.config = MagicMock()
        service.config.repo = "test/repo"

        with patch("vibe3.domain.qualify_gate.resume_issue"):
            service._auto_resume_blocked(
                issue_number=100,
                branch="test-branch",
                labels=["state/ready"],
                flow_state={
                    "flow_status": "blocked",
                    "branch": "test-branch",
                    "flow_slug": "test-slug",
                },
            )

            # Should NOT call store directly
            service._store.update_flow_state.assert_not_called()
            service._store.add_event.assert_not_called()
