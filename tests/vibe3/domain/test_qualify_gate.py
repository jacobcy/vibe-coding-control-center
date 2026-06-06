"""Unit tests for QualifyGateService domain logic.

Tests for core run_qualify_gate, qualify_blocked_issue, and dependency checking.
Remote coordination and blocked state tests are in test_qualify_gate_remote.py
and test_qualify_gate_service_calls.py respectively.
GitHub closed-state (Step 0) tests are in test_qualify_gate_closed.py.
"""

from unittest.mock import MagicMock, Mock, patch

import pytest

from vibe3.domain.qualify_gate import QualifyGateService
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.models.orchestration import IssueInfo, IssueState


@pytest.fixture
def mock_config():
    """Create a mock orchestra config."""
    return OrchestraConfig(repo="test/repo")


@pytest.fixture
def mock_github():
    """Create a mock GitHub client."""
    return Mock()


@pytest.fixture
def mock_store():
    """Create a mock SQLite client."""
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
    """Create a mock FlowManager."""
    return Mock()


@pytest.fixture
def qualify_gate_service(mock_config, mock_github, mock_store, mock_flow_manager):
    """Create a QualifyGateService instance with mocked remote collaboration."""
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


@pytest.fixture
def sample_issue():
    """Create a sample issue."""
    return IssueInfo(
        number=123,
        title="Test Issue",
        state=IssueState.IN_PROGRESS,
        labels=["state/in-progress"],
        assignees=["alice"],
    )


class TestRunQualifyGate:
    """Tests for run_qualify_gate method."""

    def test_no_flow_state_not_blocked(
        self, qualify_gate_service, sample_issue, mock_config
    ):
        """Issue with no flow state and not blocked should return trigger state."""
        result = qualify_gate_service.run_qualify_gate(
            issue=sample_issue,
            branch="task/issue-123-test",
            flow_state=None,
            labels=["state/in-progress"],
            trigger_state=IssueState.IN_PROGRESS,
        )
        assert result == IssueState.IN_PROGRESS

    def test_no_flow_state_but_blocked(
        self, qualify_gate_service, sample_issue, mock_config
    ):
        """Issue with no flow state but blocked label should return None."""
        result = qualify_gate_service.run_qualify_gate(
            issue=sample_issue,
            branch="task/issue-123-test",
            flow_state=None,
            labels=["state/blocked"],
            trigger_state=IssueState.IN_PROGRESS,
        )
        assert result is None

    def test_no_flow_state_wrong_label(
        self, qualify_gate_service, sample_issue, mock_config
    ):
        """Issue with no flow state and wrong label should return None."""
        result = qualify_gate_service.run_qualify_gate(
            issue=sample_issue,
            branch="task/issue-123-test",
            flow_state=None,
            labels=["state/ready"],
            trigger_state=IssueState.IN_PROGRESS,
        )
        assert result is None

    def test_manual_block_sets_blocked_label(
        self, qualify_gate_service, sample_issue, mock_store
    ):
        """Issue with blocked_reason should get state/blocked label."""
        flow_state = {
            "blocked_reason": "Manual intervention required",
            "branch": "task/issue-123-test",
            "flow_slug": "test-slug",
        }
        # Configure mock_store to return flow_state for FlowService
        mock_store.get_flow_state.return_value = flow_state

        mock_truth = Mock()
        mock_truth.is_blocked = True
        mock_truth.blocked_reason = "Manual intervention required"
        mock_truth.blocked_by_issue = None
        mock_truth.dependencies = []

        with patch.object(
            qualify_gate_service._coordination_resolver,
            "resolve_coordination",
            return_value=mock_truth,
        ):
            mock_label_service = Mock()
            with patch(
                "vibe3.services.LabelService",
                return_value=mock_label_service,
            ):
                result = qualify_gate_service.run_qualify_gate(
                    issue=sample_issue,
                    branch="task/issue-123-test",
                    flow_state=flow_state,
                    labels=["state/in-progress"],
                    trigger_state=IssueState.IN_PROGRESS,
                )

                assert result is None
                # BlockedStateService writes cache via update_flow_state
                mock_store.update_flow_state.assert_called()
                # LabelService confirms the blocked state
                mock_label_service.confirm_issue_state.assert_called_once()

    def test_manual_block_already_has_label(
        self, qualify_gate_service, sample_issue, mock_store
    ):
        """Issue already blocked should not attempt to add label again."""
        flow_state = {
            "blocked_reason": "Manual intervention required",
            "branch": "task/issue-123-test",
            "flow_slug": "test-slug",
        }
        # Configure mock_store to return flow_state for FlowService
        mock_store.get_flow_state.return_value = flow_state

        mock_label_port = Mock()
        with patch("vibe3.services.LabelService", return_value=mock_label_port):
            mock_truth = Mock()
            mock_truth.is_blocked = True
            mock_truth.blocked_reason = "Manual intervention required"
            mock_truth.blocked_by_issue = None
            mock_truth.dependencies = []

            with patch.object(
                qualify_gate_service._coordination_resolver,
                "resolve_coordination",
                return_value=mock_truth,
            ):
                result = qualify_gate_service.run_qualify_gate(
                    issue=sample_issue,
                    branch="task/issue-123-test",
                    flow_state=flow_state,
                    labels=["state/blocked"],
                    trigger_state=IssueState.IN_PROGRESS,
                )

                assert result is None
                mock_label_port.confirm_issue_state.assert_not_called()

    def test_dependency_block(
        self, qualify_gate_service, sample_issue, mock_store, mock_github
    ):
        """Issue with unresolved dependency should be blocked."""
        qualify_gate_service._is_dependency_satisfied = Mock(return_value=False)

        mock_store.get_flow_state.return_value = {
            "branch": "task/issue-123-test",
            "flow_status": "active",
        }
        mock_store.get_issue_links.return_value = [
            {"issue_number": 123, "issue_role": "task"}
        ]

        mock_truth = Mock()
        mock_truth.is_blocked = False
        mock_truth.blocked_reason = None
        mock_truth.blocked_by_issue = None
        mock_truth.dependencies = [456]
        mock_truth.worktree_path = None

        mock_github.get_issue_body.return_value = "User content"

        with patch.object(
            qualify_gate_service._coordination_resolver,
            "resolve_coordination",
            return_value=mock_truth,
        ):
            with patch(
                "vibe3.services.blocked_state_io.GitHubClient",
                return_value=mock_github,
            ):
                flow_state = {"status": "active"}

                result = qualify_gate_service.run_qualify_gate(
                    issue=sample_issue,
                    branch="task/issue-123-test",
                    flow_state=flow_state,
                    labels=["state/in-progress"],
                    trigger_state=IssueState.IN_PROGRESS,
                )

                assert result is None
                # BlockedStateService.block() updates flow state with blocked info
                mock_store.update_flow_state.assert_called()
                mock_store.add_event.assert_called()

    def test_dependency_satisfied(self, qualify_gate_service, sample_issue, mock_store):
        """Issue with satisfied dependency should pass gate."""
        qualify_gate_service._is_dependency_satisfied = Mock(return_value=True)

        mock_truth = Mock()
        mock_truth.is_blocked = False
        mock_truth.blocked_reason = None
        mock_truth.blocked_by_issue = None
        mock_truth.dependencies = [456]
        mock_truth.worktree_path = None

        with patch.object(
            qualify_gate_service._coordination_resolver,
            "resolve_coordination",
            return_value=mock_truth,
        ):
            flow_state = {}

            result = qualify_gate_service.run_qualify_gate(
                issue=sample_issue,
                branch="task/issue-123-test",
                flow_state=flow_state,
                labels=["state/in-progress"],
                trigger_state=IssueState.IN_PROGRESS,
            )

            assert result == IssueState.IN_PROGRESS

    def test_unblock_from_blocked_state(
        self, qualify_gate_service, sample_issue, mock_store
    ):
        """Blocked issue with cleared dependencies should auto-resume.

        When body truth is NOT blocked but local cache says blocked,
        qualify-gate auto-resumes by clearing stale blocked state.
        """
        qualify_gate_service._is_dependency_satisfied = Mock(return_value=True)

        flow_state = {
            "blocked_by_issue": 456,
            "branch": "task/issue-123-test",
            "flow_slug": "test-slug",
        }

        mock_truth = Mock()
        mock_truth.is_blocked = False
        mock_truth.blocked_reason = None
        mock_truth.blocked_by_issue = None
        mock_truth.dependencies = []
        mock_truth.worktree_path = None

        with patch.object(
            qualify_gate_service._coordination_resolver,
            "resolve_coordination",
            return_value=mock_truth,
        ):
            from vibe3.models.flow import FlowState

            with patch.object(FlowState, "model_validate") as mock_validate:
                mock_fs = Mock()
                mock_validate.return_value = mock_fs

                with patch(
                    "vibe3.domain.qualify_gate.infer_resume_label",
                    return_value=IssueState.IN_PROGRESS,
                ):
                    with patch(
                        "vibe3.domain.qualify_gate.TaskResumeOperations"
                    ) as mock_operations_cls:
                        mock_operations = MagicMock()
                        mock_operations_cls.return_value = mock_operations

                        result = qualify_gate_service.run_qualify_gate(
                            issue=sample_issue,
                            branch="task/issue-123-test",
                            flow_state=flow_state,
                            labels=["state/blocked"],
                            trigger_state=IssueState.BLOCKED,
                        )

                        assert result == IssueState.IN_PROGRESS
                        mock_operations.reset_issue_to_ready.assert_called_once()
                        call = mock_operations.reset_issue_to_ready.call_args.kwargs
                        assert call["issue_number"] == sample_issue.number
                        assert call["label_state"] == ""

    def test_unblock_with_stale_local_cache_without_blocked_label(
        self, qualify_gate_service, sample_issue, mock_store, mock_github
    ):
        """Stale local blocked cache should auto-resume even without blocked label."""
        qualify_gate_service._is_dependency_satisfied = Mock(return_value=True)

        flow_state = {
            "blocked_by_issue": 456,
            "branch": "task/issue-123-test",
            "flow_slug": "test-slug",
        }
        # Configure mock_store to return flow_state for service layer
        mock_store.get_flow_state.return_value = {
            "flow_status": "active",
            "issue_number": 123,
            "branch": "task/issue-123-test",
            "flow_slug": "test-slug",
        }

        mock_truth = Mock()
        mock_truth.is_blocked = False
        mock_truth.blocked_reason = None
        mock_truth.blocked_by_issue = None
        mock_truth.dependencies = []
        mock_truth.worktree_path = None

        mock_github.get_issue_body.return_value = "User content"

        with patch.object(
            qualify_gate_service._coordination_resolver,
            "resolve_coordination",
            return_value=mock_truth,
        ):
            from vibe3.models.flow import FlowState

            with patch.object(FlowState, "model_validate") as mock_validate:
                mock_fs = Mock()
                mock_validate.return_value = mock_fs

                with patch(
                    "vibe3.domain.qualify_gate.infer_resume_label",
                    return_value=IssueState.IN_PROGRESS,
                ):
                    with patch(
                        "vibe3.domain.qualify_gate.TaskResumeOperations"
                    ) as mock_operations_cls:
                        mock_operations = Mock()
                        mock_operations_cls.return_value = mock_operations

                        result = qualify_gate_service.run_qualify_gate(
                            issue=sample_issue,
                            branch="task/issue-123-test",
                            flow_state=flow_state,
                            labels=["state/in-progress"],
                            trigger_state=IssueState.IN_PROGRESS,
                        )

                        assert result == IssueState.IN_PROGRESS


class TestQualifyBlockedIssue:
    """Tests for qualify_blocked_issue method."""

    def test_qualify_blocked_issue_no_branch(
        self, qualify_gate_service, sample_issue, mock_flow_manager
    ):
        """Issue with no branch should return None."""
        mock_flow_manager.get_flow_for_issue.return_value = None

        result = qualify_gate_service.qualify_blocked_issue(sample_issue)

        assert result is None

    def test_qualify_blocked_issue_success(
        self, qualify_gate_service, sample_issue, mock_flow_manager, mock_store
    ):
        """Blocked issue should be qualified successfully."""
        mock_flow_manager.get_flow_for_issue.return_value = {
            "branch": "task/issue-123-test"
        }
        mock_store.get_flow_state.return_value = {}

        # Mock run_qualify_gate to return IN_PROGRESS
        qualify_gate_service.run_qualify_gate = Mock(
            return_value=IssueState.IN_PROGRESS
        )

        result = qualify_gate_service.qualify_blocked_issue(sample_issue)

        assert result == IssueState.IN_PROGRESS
        qualify_gate_service.run_qualify_gate.assert_called_once()


class TestIsDependencySatisfied:
    """Tests for _is_dependency_satisfied method."""

    def test_issue_closed(self, qualify_gate_service, mock_github):
        """Closed issue should satisfy dependency."""
        mock_github.view_issue.return_value = {"state": "closed"}

        result = qualify_gate_service._is_dependency_satisfied(456)

        assert result is True

    def test_issue_open(self, qualify_gate_service, mock_github):
        """Open issue should not satisfy dependency."""
        mock_github.view_issue.return_value = {"state": "open"}

        result = qualify_gate_service._is_dependency_satisfied(456)

        assert result is False

    def test_invalid_payload(self, qualify_gate_service, mock_github):
        """Invalid payload should not satisfy dependency."""
        mock_github.view_issue.return_value = None

        result = qualify_gate_service._is_dependency_satisfied(456)

        assert result is False

    def test_qualify_blocked_closed_issue_terminalizes_flow(
        self, qualify_gate_service, mock_store, mock_flow_manager
    ):
        """Blocked issue closed on GitHub should terminalize flow and skip."""
        closed_issue = IssueInfo(
            number=999,
            title="Closed Blocked Issue",
            state=IssueState.BLOCKED,
            labels=["state/blocked"],
            github_state="CLOSED",
        )
        mock_flow_manager.get_flow_for_issue.return_value = {"branch": "task/issue-999"}

        result = qualify_gate_service.qualify_blocked_issue(closed_issue)

        assert result is None
        # Now uses FlowCleanupService instead of soft_delete_flow
        # FlowCleanupService.cleanup_flow_scene should be called
        # We verify that soft_delete_flow is NOT called directly
        mock_store.soft_delete_flow.assert_not_called()

    def test_qualify_blocked_closed_no_flow_skips(
        self, qualify_gate_service, mock_store, mock_flow_manager
    ):
        """Closed issue without local flow should skip without error."""
        closed_issue = IssueInfo(
            number=998,
            title="Closed No Flow",
            state=IssueState.BLOCKED,
            labels=["state/blocked"],
            github_state="CLOSED",
        )
        mock_flow_manager.get_flow_for_issue.return_value = None

        result = qualify_gate_service.qualify_blocked_issue(closed_issue)

        assert result is None
        mock_store.soft_delete_flow.assert_not_called()


def test_auto_resume_blocked_uses_task_resume_operations() -> None:
    """QualifyGate auto-resume must share task resume --label auto semantics."""
    from unittest.mock import MagicMock, patch

    from vibe3.domain.qualify_gate import QualifyGateService
    from vibe3.models.orchestra_config import OrchestraConfig
    from vibe3.models.orchestration import IssueState

    service = QualifyGateService(
        OrchestraConfig(repo="owner/repo"),
        MagicMock(),
        MagicMock(),
        MagicMock(),
    )
    service._store.get_flow_state.return_value = {
        "branch": "task/issue-303",
        "flow_slug": "issue-303",
        "flow_status": "blocked",
        "latest_actor": "test",
        "task_issue_number": 303,
    }

    with patch("vibe3.domain.qualify_gate.TaskResumeOperations") as operations_cls:
        operations = MagicMock()
        operations_cls.return_value = operations

        result = service._auto_resume_blocked(
            issue_number=303,
            branch="task/issue-303",
            labels=["state/blocked"],
            flow_state=service._store.get_flow_state.return_value,
        )

        operations.reset_issue_to_ready.assert_called_once()
        call = operations.reset_issue_to_ready.call_args.kwargs
        assert call["issue_number"] == 303
        assert call["label_state"] == ""
        assert result != IssueState.BLOCKED


def test_auto_resume_blocked_with_none_flow_state_returns_ready() -> None:
    """When flow_state is None, _auto_resume_blocked should return READY."""
    from unittest.mock import MagicMock, patch

    from vibe3.domain.qualify_gate import QualifyGateService
    from vibe3.models.orchestra_config import OrchestraConfig
    from vibe3.models.orchestration import IssueState

    service = QualifyGateService(
        OrchestraConfig(repo="owner/repo"), MagicMock(), MagicMock(), MagicMock()
    )

    with patch("vibe3.domain.qualify_gate.TaskResumeOperations"):
        result = service._auto_resume_blocked(
            issue_number=303,
            branch="task/issue-303",
            labels=["state/blocked"],
            flow_state=None,
        )

        assert result == IssueState.READY
