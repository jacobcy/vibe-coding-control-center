"""Test qualify_gate local blocked state synchronization helpers."""

from unittest.mock import MagicMock, Mock, patch

from vibe3.domain.qualify_gate import QualifyGateService
from vibe3.models.orchestration import IssueState


class TestAlignBlockedState:
    """Test _align_blocked_state updates local cache idempotently."""

    def test_aligns_local_cache_and_missing_label(self):
        """Blocked truth should sync local cache and add the blocked label."""
        service = QualifyGateService.__new__(QualifyGateService)
        service._store = MagicMock()
        service._github = Mock()
        service._convention = Mock()
        service._convention.blocked_label = "blocked"
        service._convention.state_label = Mock(return_value="state/blocked")
        service.config = MagicMock()
        service.config.repo = "test/repo"

        truth = MagicMock(
            blocked_reason="dependency issue",
            blocked_by_issues=[200],
        )
        truth.blocked_by_issue = 200  # computed property returns first element

        mock_label_service = MagicMock()
        with patch("vibe3.services.LabelService", return_value=mock_label_service):
            service._align_blocked_state(
                issue_number=100,
                branch="test-branch",
                truth=truth,
                labels=["state/in-progress"],
                flow_state={"flow_status": "active"},
            )

        # BlockedStateService.write_cache updates the flow state
        service._store.update_flow_state.assert_called_once()
        call_kwargs = service._store.update_flow_state.call_args[1]
        assert call_kwargs["flow_status"] == "blocked"
        assert call_kwargs["blocked_reason"] == "dependency issue"
        assert call_kwargs["blocked_by_issue"] == 200
        mock_label_service.confirm_issue_state.assert_called_once_with(
            100, IssueState.BLOCKED, actor="orchestra:qualify_gate", force=True
        )

    def test_does_not_rewrite_when_already_blocked_and_labeled(self):
        """Already-synced blocked state should not write local cache again."""
        service = QualifyGateService.__new__(QualifyGateService)
        service._store = MagicMock()
        service._github = Mock()
        service._convention = Mock()
        service._convention.blocked_label = "blocked"
        service._convention.state_label = Mock(return_value="state/blocked")
        service.config = MagicMock()
        service.config.repo = "test/repo"

        truth = MagicMock(
            blocked_reason="test reason",
            blocked_by_issue=None,
        )

        mock_label_service = MagicMock()
        with patch("vibe3.services.LabelService", return_value=mock_label_service):
            service._align_blocked_state(
                issue_number=100,
                branch="test-branch",
                truth=truth,
                labels=["state/blocked"],
                flow_state={"flow_status": "blocked"},
            )

        service._store.update_flow_state.assert_not_called()
        mock_label_service.confirm_issue_state.assert_not_called()


class TestAutoResumeBlocked:
    """Test _auto_resume_blocked clears local blocked cache directly."""

    def test_uses_blocked_state_service(self):
        """Auto-resume should use TaskResumeOperations.reset_issue_to_ready."""
        service = QualifyGateService.__new__(QualifyGateService)
        service._store = MagicMock()
        service._github = Mock()
        service._convention = Mock()
        service._convention.blocked_label = "blocked"
        service._convention.state_label = Mock(return_value="state/blocked")
        service.config = MagicMock()
        service.config.repo = "test/repo"

        with patch(
            "vibe3.domain.qualify_gate.infer_resume_label",
            return_value=IssueState.READY,
        ):
            with patch("vibe3.models.flow.FlowState.model_validate"):
                with patch(
                    "vibe3.domain.qualify_gate.TaskResumeOperations"
                ) as mock_operations_cls:
                    mock_operations = MagicMock()
                    mock_operations_cls.return_value = mock_operations

                    result = service._auto_resume_blocked(
                        issue_number=100,
                        branch="test-branch",
                        labels=["state/blocked"],
                        flow_state={
                            "flow_status": "blocked",
                            "branch": "test-branch",
                            "flow_slug": "test-slug",
                        },
                    )

        mock_operations.reset_issue_to_ready.assert_called_once()
        call = mock_operations.reset_issue_to_ready.call_args.kwargs
        assert call["issue_number"] == 100
        assert call["label_state"] == ""
        assert result == IssueState.READY

    def test_skips_label_sync_when_blocked_label_missing(self):
        """Without blocked label, auto-resume still uses TaskResumeOperations."""
        service = QualifyGateService.__new__(QualifyGateService)
        service._store = MagicMock()
        service._github = Mock()
        service._convention = Mock()
        service._convention.blocked_label = "blocked"
        service._convention.state_label = Mock(return_value="state/blocked")
        service.config = MagicMock()
        service.config.repo = "test/repo"

        with patch(
            "vibe3.domain.qualify_gate.infer_resume_label",
            return_value=IssueState.CLAIMED,
        ):
            with patch("vibe3.models.flow.FlowState.model_validate"):
                with patch(
                    "vibe3.domain.qualify_gate.TaskResumeOperations"
                ) as mock_operations_cls:
                    mock_operations = MagicMock()
                    mock_operations_cls.return_value = mock_operations

                    result = service._auto_resume_blocked(
                        issue_number=100,
                        branch="test-branch",
                        labels=["state/in-progress"],
                        flow_state={
                            "flow_status": "blocked",
                            "branch": "test-branch",
                            "flow_slug": "test-slug",
                        },
                    )

        mock_operations.reset_issue_to_ready.assert_called_once()
        call = mock_operations.reset_issue_to_ready.call_args.kwargs
        assert call["issue_number"] == 100
        assert call["label_state"] == ""
        assert result == IssueState.CLAIMED
