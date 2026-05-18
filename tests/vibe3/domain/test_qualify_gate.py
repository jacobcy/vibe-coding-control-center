"""Unit tests for QualifyGateService domain logic."""

from unittest.mock import Mock, patch

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
    # NEW: Mock methods needed by CoordinationResolver
    store.get_flow_state = Mock(return_value=None)
    store.get_dependency_links = Mock(return_value=[])
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
    # Mock remote collaboration read to return empty (unblocked) state
    with patch.object(
        service._coordination_resolver,
        "_read_remote_collaboration",
        return_value={
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
        mock_label_port = Mock()
        with patch(
            "vibe3.domain.qualify_gate.GhIssueLabelPort", return_value=mock_label_port
        ):
            flow_state = {"blocked_reason": "Manual intervention required"}
            # NEW: Mock CoordinationResolver to use flow_state
            mock_truth = Mock()
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
                    labels=["state/in-progress"],
                    trigger_state=IssueState.IN_PROGRESS,
                )

                assert result is None
                mock_label_port.add_issue_label.assert_called_once_with(
                    123, "state/blocked"
                )

    def test_manual_block_already_has_label(
        self, qualify_gate_service, sample_issue, mock_store
    ):
        """Issue already blocked should not attempt to add label again."""
        mock_label_port = Mock()
        with patch(
            "vibe3.domain.qualify_gate.GhIssueLabelPort", return_value=mock_label_port
        ):
            flow_state = {"blocked_reason": "Manual intervention required"}
            # NEW: Mock CoordinationResolver to use flow_state
            mock_truth = Mock()
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
                mock_label_port.add_issue_label.assert_not_called()

    def test_dependency_block(
        self, qualify_gate_service, sample_issue, mock_store, mock_github
    ):
        """Issue with unresolved dependency should be blocked."""
        # Setup dependencies
        qualify_gate_service._is_dependency_satisfied = Mock(return_value=False)

        # Mock store.get_flow_state for FlowService.block_flow()
        mock_store.get_flow_state.return_value = {
            "branch": "task/issue-123-test",
            "flow_status": "active",
        }
        # Mock get_issue_links for LabelService.transition
        mock_store.get_issue_links.return_value = [
            {"issue_number": 123, "issue_role": "task"}
        ]

        with patch(
            "vibe3.services.flow_block_mixin.LabelService"
        ) as mock_label_service_cls:
            mock_label_service = Mock()
            mock_label_service_cls.return_value = mock_label_service

            # NEW: Mock CoordinationResolver to return dependencies
            mock_truth = Mock()
            mock_truth.blocked_reason = None
            mock_truth.blocked_by_issue = None
            mock_truth.dependencies = [456]
            mock_truth.worktree_path = None

            with patch.object(
                qualify_gate_service._coordination_resolver,
                "resolve_coordination",
                return_value=mock_truth,
            ):
                # Use non-empty flow_state to avoid early return
                flow_state = {"status": "active"}

                result = qualify_gate_service.run_qualify_gate(
                    issue=sample_issue,
                    branch="task/issue-123-test",
                    flow_state=flow_state,
                    labels=["state/in-progress"],
                    trigger_state=IssueState.IN_PROGRESS,
                )

                assert result is None
                mock_store.update_flow_state.assert_called()
                # Verify LabelService.transition was called
                mock_label_service.transition.assert_called_once()
                mock_store.add_event.assert_called()

    def test_dependency_satisfied(self, qualify_gate_service, sample_issue, mock_store):
        """Issue with satisfied dependency should pass gate."""
        qualify_gate_service._is_dependency_satisfied = Mock(return_value=True)

        # NEW: Mock CoordinationResolver to return dependencies
        mock_truth = Mock()
        mock_truth.blocked_reason = None
        mock_truth.blocked_by_issue = None
        mock_truth.dependencies = [456]

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
        """Blocked issue with cleared dependencies should unblock."""
        qualify_gate_service._is_dependency_satisfied = Mock(return_value=True)

        mock_label_port = Mock()
        with patch(
            "vibe3.domain.qualify_gate.GhIssueLabelPort",
            return_value=mock_label_port,
        ):
            # NEW: Mock CoordinationResolver to return
            # blocked_by_issue but no dependencies
            mock_truth = Mock()
            mock_truth.blocked_reason = None
            mock_truth.blocked_by_issue = 456
            mock_truth.dependencies = []

            with patch.object(
                qualify_gate_service._coordination_resolver,
                "resolve_coordination",
                return_value=mock_truth,
            ):
                # Mock flow state with blocked_by_issue but no blocked_reason
                # (blocked_reason: manual blocks; blocked_by_issue: dependency blocks)
                flow_state = {
                    "blocked_by_issue": 456,
                }

                # Mock FlowState model
                from vibe3.models.flow import FlowState

                mock_flow_state_obj = Mock()
                mock_flow_state_obj.status = "active"
                mock_flow_state_obj.issue_number = 123
                mock_flow_state_obj.branch = "task/issue-123-test"
                mock_flow_state_obj.issue_title = "Test Issue"

                with patch.object(
                    FlowState, "model_validate", return_value=mock_flow_state_obj
                ):
                    # Mock infer_resume_label
                    with patch(
                        "vibe3.domain.qualify_gate.infer_resume_label",
                        return_value=IssueState.IN_PROGRESS,
                    ):
                        # Mock get_flows_by_issue for source_pr lookup
                        mock_store.get_flows_by_issue.return_value = []

                        result = qualify_gate_service.run_qualify_gate(
                            issue=sample_issue,
                            branch="task/issue-123-test",
                            flow_state=flow_state,
                            labels=["state/blocked"],
                            trigger_state=IssueState.BLOCKED,
                        )

                        assert result == IssueState.IN_PROGRESS
                        mock_store.update_flow_state.assert_called()
                        mock_store.add_event.assert_called()
                        mock_label_port.remove_issue_label.assert_called_once_with(
                            123, "state/blocked"
                        )
                        mock_label_port.add_issue_label.assert_called_once_with(
                            123, "state/in-progress"
                        )


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
