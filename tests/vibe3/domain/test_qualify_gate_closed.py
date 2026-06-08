"""Tests for QualifyGate GitHub closed issue detection (Step 0).

Covers run_qualify_gate early exit when GitHub state is CLOSED,
extracted from test_qualify_gate.py to keep file sizes manageable.
"""

from unittest.mock import Mock, patch

import pytest

from vibe3.domain.qualify_gate import QualifyGateService
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.models.orchestration import IssueInfo, IssueState


@pytest.fixture
def mock_config():
    return OrchestraConfig(repo="test/repo")


@pytest.fixture
def mock_github():
    return Mock()


@pytest.fixture
def mock_store():
    store = Mock()
    store.db_path = ":memory:"
    store.get_flow_state = Mock(return_value=None)
    store.get_dependency_links = Mock(return_value=[])
    store.get_issue_links = Mock(return_value=[])
    store.update_flow_state = Mock()
    store.add_event = Mock()
    return store


@pytest.fixture
def mock_flow_manager():
    return Mock()


@pytest.fixture
def qualify_gate_service(mock_config, mock_github, mock_store, mock_flow_manager):
    service = QualifyGateService(
        config=mock_config,
        github=mock_github,
        store=mock_store,
        flow_manager=mock_flow_manager,
    )
    with patch.object(
        service._coordination_resolver,
        "_read_remote_collaboration",
        return_value={
            "projection_state": "active",
            "blocked_reason": None,
            "blocked_by_issue": None,
            "dependencies": [],
        },
    ):
        yield service


class TestQualifyGateGitHubClosed:
    """Tests for run_qualify_gate GitHub closed check (Step 0, all states).

    Step 0 terminates immediately for CLOSED issues before any business logic.
    """

    def _run_with_closed_issue(
        self,
        qualify_gate_service: QualifyGateService,
        issue_number: int,
        state: IssueState,
        labels: list[str],
        explicit_branch: str = "auto",
    ) -> tuple[object, Mock, Mock]:
        """Run qualify gate for a CLOSED issue.

        Returns (result, mock_cleanup_svc, mock_flow_status_svc).
        Pass explicit_branch="" to test the empty-branch code path.
        """
        effective_branch = (
            f"task/issue-{issue_number}"
            if explicit_branch == "auto"
            else explicit_branch
        )
        closed_issue = IssueInfo(
            number=issue_number,
            title=f"Closed Issue #{issue_number}",
            state=state,
            labels=labels,
            github_state="CLOSED",
        )
        with (
            patch(
                "vibe3.domain.qualify_gate.FlowStatusService"
            ) as mock_flow_status_svc,
            patch("vibe3.services.FlowCleanupService") as mock_cleanup_svc,
        ):
            result = qualify_gate_service.run_qualify_gate(
                issue=closed_issue,
                branch=effective_branch,
                flow_state={"flow_status": "active"},
                labels=labels,
                trigger_state=state,
            )
        return result, mock_cleanup_svc, mock_flow_status_svc

    def test_closed_ready_issue_terminates(
        self, qualify_gate_service: QualifyGateService
    ) -> None:
        """READY + CLOSED → None and cleanup_flow_scene called with correct args."""
        result, mock_cleanup_svc, mock_flow_status_svc = self._run_with_closed_issue(
            qualify_gate_service, 101, IssueState.READY, ["state/ready"]
        )

        assert result is None

        # Verify mark_flow_aborted is called
        mock_flow_status_svc.return_value.mark_flow_aborted.assert_called_once_with(
            "task/issue-101",
            "Issue #101 closed on GitHub",
        )

        # Verify cleanup_flow_scene is called
        mock_cleanup_svc.return_value.cleanup_flow_scene.assert_called_once_with(
            "task/issue-101",
            include_remote=False,
            terminate_sessions=True,
            keep_flow_record=True,
        )

    def test_closed_claimed_issue_terminates(
        self, qualify_gate_service: QualifyGateService
    ) -> None:
        """CLAIMED + CLOSED → None and cleanup_flow_scene called with correct args."""
        result, mock_cleanup_svc, mock_flow_status_svc = self._run_with_closed_issue(
            qualify_gate_service, 102, IssueState.CLAIMED, ["state/claimed"]
        )

        assert result is None

        # Verify mark_flow_aborted is called
        mock_flow_status_svc.return_value.mark_flow_aborted.assert_called_once_with(
            "task/issue-102",
            "Issue #102 closed on GitHub",
        )

        # Verify cleanup_flow_scene is called
        mock_cleanup_svc.return_value.cleanup_flow_scene.assert_called_once_with(
            "task/issue-102",
            include_remote=False,
            terminate_sessions=True,
            keep_flow_record=True,
        )

    def test_closed_in_progress_issue_terminates(
        self, qualify_gate_service: QualifyGateService
    ) -> None:
        """IN_PROGRESS + CLOSED → None and cleanup_flow_scene called correctly."""
        result, mock_cleanup_svc, mock_flow_status_svc = self._run_with_closed_issue(
            qualify_gate_service, 103, IssueState.IN_PROGRESS, ["state/in-progress"]
        )

        assert result is None

        # Verify mark_flow_aborted is called
        mock_flow_status_svc.return_value.mark_flow_aborted.assert_called_once_with(
            "task/issue-103",
            "Issue #103 closed on GitHub",
        )

        # Verify cleanup_flow_scene is called
        mock_cleanup_svc.return_value.cleanup_flow_scene.assert_called_once_with(
            "task/issue-103",
            include_remote=False,
            terminate_sessions=True,
            keep_flow_record=True,
        )

    def test_open_issue_skips_closed_check(
        self, qualify_gate_service: QualifyGateService
    ) -> None:
        """OPEN issue → closed check not triggered, normal gate logic runs."""
        open_issue = IssueInfo(
            number=104,
            title="Open Issue",
            state=IssueState.READY,
            labels=["state/ready"],
            github_state="OPEN",
        )
        result = qualify_gate_service.run_qualify_gate(
            issue=open_issue,
            branch="task/issue-104",
            flow_state=None,
            labels=["state/ready"],
            trigger_state=IssueState.READY,
        )
        assert result == IssueState.READY

    def test_none_github_state_skips_closed_check(
        self, qualify_gate_service: QualifyGateService
    ) -> None:
        """github_state=None → closed check not triggered, normal gate logic runs."""
        issue = IssueInfo(
            number=105,
            title="Issue No GitHub State",
            state=IssueState.READY,
            labels=["state/ready"],
            github_state=None,
        )
        result = qualify_gate_service.run_qualify_gate(
            issue=issue,
            branch="task/issue-105",
            flow_state=None,
            labels=["state/ready"],
            trigger_state=IssueState.READY,
        )
        assert result == IssueState.READY

    def test_closed_empty_branch_skips_cleanup(
        self, qualify_gate_service: QualifyGateService
    ) -> None:
        """CLOSED issue with empty branch → returns None but cleanup not called."""
        result, mock_cleanup_svc, mock_flow_status_svc = self._run_with_closed_issue(
            qualify_gate_service,
            106,
            IssueState.READY,
            ["state/ready"],
            explicit_branch="",
        )

        assert result is None
        mock_cleanup_svc.assert_not_called()
        mock_flow_status_svc.assert_not_called()

    def test_closed_issue_already_done_not_overwritten(
        self, qualify_gate_service: QualifyGateService
    ) -> None:
        """flow_status=done → mark_flow_aborted NOT called.

        cleanup_flow_scene still called.
        """
        # Setup flow_state with done status
        qualify_gate_service._store.get_flow_state = Mock(
            return_value={"flow_status": "done"}
        )

        result, mock_cleanup_svc, mock_flow_status_svc = self._run_with_closed_issue(
            qualify_gate_service, 107, IssueState.READY, ["state/ready"]
        )

        assert result is None

        # Verify mark_flow_aborted is NOT called (already done)
        mock_flow_status_svc.return_value.mark_flow_aborted.assert_not_called()

        # Verify cleanup_flow_scene is still called
        mock_cleanup_svc.return_value.cleanup_flow_scene.assert_called_once_with(
            "task/issue-107",
            include_remote=False,
            terminate_sessions=True,
            keep_flow_record=True,
        )

    def test_closed_issue_already_aborted_not_overwritten(
        self, qualify_gate_service: QualifyGateService
    ) -> None:
        """flow_status=aborted → mark_flow_aborted NOT called.

        cleanup_flow_scene still called.
        """
        # Setup flow_state with aborted status
        qualify_gate_service._store.get_flow_state = Mock(
            return_value={"flow_status": "aborted"}
        )

        result, mock_cleanup_svc, mock_flow_status_svc = self._run_with_closed_issue(
            qualify_gate_service, 108, IssueState.READY, ["state/ready"]
        )

        assert result is None

        # Verify mark_flow_aborted is NOT called (already aborted)
        mock_flow_status_svc.return_value.mark_flow_aborted.assert_not_called()

        # Verify cleanup_flow_scene is still called
        mock_cleanup_svc.return_value.cleanup_flow_scene.assert_called_once_with(
            "task/issue-108",
            include_remote=False,
            terminate_sessions=True,
            keep_flow_record=True,
        )

    def test_closed_issue_no_flow_state_marks_aborted(
        self, qualify_gate_service: QualifyGateService
    ) -> None:
        """flow_state=None → mark_flow_aborted IS called.

        Treats missing state as non-terminal.
        """
        # Setup flow_state as None (no flow record exists)
        qualify_gate_service._store.get_flow_state = Mock(return_value=None)

        result, mock_cleanup_svc, mock_flow_status_svc = self._run_with_closed_issue(
            qualify_gate_service, 109, IssueState.READY, ["state/ready"]
        )

        assert result is None

        # Verify mark_flow_aborted IS called (missing state treated as non-terminal)
        mock_flow_status_svc.return_value.mark_flow_aborted.assert_called_once_with(
            "task/issue-109",
            "Issue #109 closed on GitHub",
        )

        # Verify cleanup_flow_scene is still called
        mock_cleanup_svc.return_value.cleanup_flow_scene.assert_called_once_with(
            "task/issue-109",
            include_remote=False,
            terminate_sessions=True,
            keep_flow_record=True,
        )
