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
            blocked_by_issue=200,
        )

        mock_label_port = MagicMock()
        with patch(
            "vibe3.domain.qualify_gate.GhIssueLabelPort", return_value=mock_label_port
        ):
            service._align_blocked_state(
                issue_number=100,
                branch="test-branch",
                truth=truth,
                labels=["state/in-progress"],
                flow_state={"flow_status": "active"},
            )

        service._store.update_flow_state.assert_called_once_with(
            "test-branch",
            flow_status="blocked",
            blocked_reason="dependency issue",
            blocked_by_issue=200,
            latest_actor="system:qualify_gate",
        )
        mock_label_port.add_issue_label.assert_called_once_with(100, "state/blocked")

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

        mock_label_port = MagicMock()
        with patch(
            "vibe3.domain.qualify_gate.GhIssueLabelPort", return_value=mock_label_port
        ):
            service._align_blocked_state(
                issue_number=100,
                branch="test-branch",
                truth=truth,
                labels=["state/blocked"],
                flow_state={"flow_status": "blocked"},
            )

        service._store.update_flow_state.assert_not_called()
        mock_label_port.add_issue_label.assert_not_called()


class TestAutoResumeBlocked:
    """Test _auto_resume_blocked clears local blocked cache directly."""

    def test_uses_blocked_state_service(self):
        """Auto-resume should use BlockedStateService.unblock."""
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
                    "vibe3.services.blocked_state_service.BlockedStateService"
                ) as mock_blocked_cls:
                    mock_blocked_instance = MagicMock()
                    mock_blocked_cls.return_value = mock_blocked_instance

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

        mock_blocked_instance.unblock.assert_called_once_with(
            branch="test-branch",
            target_state=IssueState.READY,
            actor="orchestra:qualify",
            issue_number=100,
        )
        assert result == IssueState.READY

    def test_skips_label_sync_when_blocked_label_missing(self):
        """Without blocked label, auto-resume still uses BlockedStateService."""
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
                    "vibe3.services.blocked_state_service.BlockedStateService"
                ) as mock_blocked_cls:
                    mock_blocked_instance = MagicMock()
                    mock_blocked_cls.return_value = mock_blocked_instance

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

        mock_blocked_instance.unblock.assert_called_once_with(
            branch="test-branch",
            target_state=IssueState.CLAIMED,
            actor="orchestra:qualify",
            issue_number=100,
        )
        assert result == IssueState.CLAIMED
