"""Tests for StatusService with FailedGate integration."""

from unittest.mock import MagicMock

from vibe3.orchestra.config import OrchestraConfig
from vibe3.orchestra.failed_gate import GateResult
from vibe3.orchestra.services.status_service import OrchestraStatusService


def test_status_snapshot_with_gate_blocked() -> None:
    config = OrchestraConfig(repo="owner/repo")
    mock_gate = MagicMock()
    mock_gate.check.return_value = GateResult(
        blocked=True,
        issue_number=123,
        reason="some failure",
    )

    # We need to mock some other components to avoid real API calls
    with MagicMock() as mock_github:
        mock_github.list_issues.return_value = []
        with MagicMock() as mock_orchestrator:
            mock_orchestrator.get_flow_for_issue.return_value = None

            service = OrchestraStatusService(
                config,
                github=mock_github,
                orchestrator=mock_orchestrator,
                failed_gate=mock_gate,
            )

            # We need to mock GitClient.list_worktrees as well
            with MagicMock() as mock_git:
                service._git = mock_git
                mock_git.list_worktrees.return_value = []

                snapshot = service.snapshot()

                assert snapshot.dispatch_blocked is True
                assert snapshot.blocked_reason == "state/failed"
                assert snapshot.blocked_issue_number == 123
                assert snapshot.blocked_issue_reason == "some failure"


def test_status_snapshot_with_gate_open() -> None:
    config = OrchestraConfig(repo="owner/repo")
    mock_gate = MagicMock()
    mock_gate.check.return_value = GateResult(blocked=False)

    with MagicMock() as mock_github:
        mock_github.list_issues.return_value = []
        with MagicMock() as mock_orchestrator:
            service = OrchestraStatusService(
                config,
                github=mock_github,
                orchestrator=mock_orchestrator,
                failed_gate=mock_gate,
            )
            with MagicMock() as mock_git:
                service._git = mock_git
                mock_git.list_worktrees.return_value = []

                snapshot = service.snapshot()

                assert snapshot.dispatch_blocked is False
                assert snapshot.blocked_reason is None
