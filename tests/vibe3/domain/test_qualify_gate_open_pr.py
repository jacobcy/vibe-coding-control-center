"""Tests for open PR detection and flow transition to review (Step 0b).

Split from test_qualify_gate.py for size management.
Related to Issue #2615: migrate open PR detection to qualify_gate layer.
"""

from unittest.mock import MagicMock, Mock, patch

import pytest

from vibe3.domain.qualify_gate import QualifyGateService
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.models.orchestration import IssueInfo, IssueState


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
def qualify_gate_service(mock_github, mock_store, mock_flow_manager):
    """Create a QualifyGateService instance with mocked remote collaboration."""
    service = QualifyGateService(
        config=OrchestraConfig(repo="test/repo"),
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


class TestOpenPRDetection:
    """Tests for open PR detection and flow transition to review (Step 0b)."""

    def test_open_pr_with_planner_running_transitions_to_review(
        self, qualify_gate_service, mock_github, mock_store
    ):
        """Active flow with open PR and running planner should transition to review."""
        from vibe3.models.pr import PRResponse, PRState

        # Mock flow state with running planner
        mock_store.get_flow_state.return_value = {
            "branch": "task/my-feature",
            "flow_slug": "my_feature",
            "flow_status": "active",
            "planner_status": "running",
        }

        # Mock open PR
        open_pr = PRResponse(
            number=42,
            title="Test PR",
            state=PRState.OPEN,
            head_branch="task/my-feature",
            base_branch="main",
            url="https://github.com/test/pr/42",
            draft=False,
            is_ready=True,
            ci_passed=True,
        )
        mock_github.list_prs_for_branch.return_value = [open_pr]

        # Mock FlowStatusService
        with patch("vibe3.services.FlowStatusService") as flow_status_cls:
            flow_status = MagicMock()
            flow_status_cls.return_value = flow_status

            with patch("vibe3.observability.append_orchestra_event"):
                # Call run_qualify_gate with branch
                result = qualify_gate_service.run_qualify_gate(
                    issue=IssueInfo(
                        number=123,
                        title="Test Issue",
                        state=IssueState.IN_PROGRESS,
                        labels=["state/in-progress"],
                        assignees=["alice"],
                    ),
                    branch="task/my-feature",
                    flow_state=mock_store.get_flow_state.return_value,
                    labels=["state/in-progress"],
                    trigger_state=IssueState.IN_PROGRESS,
                )

                # Should return None (transitioning to review)
                assert result is None
                # Should call mark_flow_status with "review"
                flow_status.mark_flow_status.assert_called_once()
                call = flow_status.mark_flow_status.call_args
                assert call[0][0] == "task/my-feature"
                assert call[0][1] == "review"

    def test_open_pr_with_executor_running_transitions_to_review(
        self, qualify_gate_service, mock_github, mock_store
    ):
        """Active flow with open PR and running executor should transition to review."""
        from vibe3.models.pr import PRResponse, PRState

        # Mock flow state with running executor
        mock_store.get_flow_state.return_value = {
            "branch": "task/my-feature",
            "flow_slug": "my_feature",
            "flow_status": "active",
            "executor_status": "running",
        }

        # Mock open PR
        open_pr = PRResponse(
            number=42,
            title="Test PR",
            state=PRState.OPEN,
            head_branch="task/my-feature",
            base_branch="main",
            url="https://github.com/test/pr/42",
            draft=False,
            is_ready=True,
            ci_passed=True,
        )
        mock_github.list_prs_for_branch.return_value = [open_pr]

        # Mock FlowStatusService
        with patch("vibe3.services.FlowStatusService") as flow_status_cls:
            flow_status = MagicMock()
            flow_status_cls.return_value = flow_status

            with patch("vibe3.observability.append_orchestra_event"):
                result = qualify_gate_service.run_qualify_gate(
                    issue=IssueInfo(
                        number=123,
                        title="Test Issue",
                        state=IssueState.IN_PROGRESS,
                        labels=["state/in-progress"],
                        assignees=["alice"],
                    ),
                    branch="task/my-feature",
                    flow_state=mock_store.get_flow_state.return_value,
                    labels=["state/in-progress"],
                    trigger_state=IssueState.IN_PROGRESS,
                )

                assert result is None
                flow_status.mark_flow_status.assert_called_once()
                call = flow_status.mark_flow_status.call_args
                assert call[0][0] == "task/my-feature"
                assert call[0][1] == "review"

    def test_open_pr_no_worker_running_does_not_transition(
        self, qualify_gate_service, mock_github, mock_store
    ):
        """Active flow with open PR but no running worker should NOT transition."""
        from vibe3.models.pr import PRResponse, PRState

        # Mock flow state with no workers running
        mock_store.get_flow_state.return_value = {
            "branch": "task/my-feature",
            "flow_slug": "my_feature",
            "flow_status": "active",
        }

        # Mock open PR
        open_pr = PRResponse(
            number=42,
            title="Test PR",
            state=PRState.OPEN,
            head_branch="task/my-feature",
            base_branch="main",
            url="https://github.com/test/pr/42",
            draft=False,
            is_ready=True,
            ci_passed=True,
        )
        mock_github.list_prs_for_branch.return_value = [open_pr]

        result = qualify_gate_service.run_qualify_gate(
            issue=IssueInfo(
                number=123,
                title="Test Issue",
                state=IssueState.IN_PROGRESS,
                labels=["state/in-progress"],
                assignees=["alice"],
            ),
            branch="task/my-feature",
            flow_state=mock_store.get_flow_state.return_value,
            labels=["state/in-progress"],
            trigger_state=IssueState.IN_PROGRESS,
        )

        # Should return trigger state (not transitioning)
        assert result == IssueState.IN_PROGRESS

    def test_open_pr_already_review_does_not_transition(
        self, qualify_gate_service, mock_github, mock_store
    ):
        """Flow already in review state should NOT transition (idempotent)."""
        from vibe3.models.pr import PRResponse, PRState

        # Mock flow state already in review
        mock_store.get_flow_state.return_value = {
            "branch": "task/my-feature",
            "flow_slug": "my_feature",
            "flow_status": "review",
            "planner_status": "running",
        }

        # Mock open PR
        open_pr = PRResponse(
            number=42,
            title="Test PR",
            state=PRState.OPEN,
            head_branch="task/my-feature",
            base_branch="main",
            url="https://github.com/test/pr/42",
            draft=False,
            is_ready=True,
            ci_passed=True,
        )
        mock_github.list_prs_for_branch.return_value = [open_pr]

        with patch("vibe3.domain.qualify_gate.FlowStatusService") as flow_status_cls:
            flow_status = MagicMock()
            flow_status_cls.return_value = flow_status

            result = qualify_gate_service.run_qualify_gate(
                issue=IssueInfo(
                    number=123,
                    title="Test Issue",
                    state=IssueState.IN_PROGRESS,
                    labels=["state/in-progress"],
                    assignees=["alice"],
                ),
                branch="task/my-feature",
                flow_state=mock_store.get_flow_state.return_value,
                labels=["state/in-progress"],
                trigger_state=IssueState.IN_PROGRESS,
            )

            # Should return trigger state (already in review)
            assert result == IssueState.IN_PROGRESS
            # Should NOT call mark_flow_status
            flow_status.mark_flow_status.assert_not_called()

    def test_open_pr_already_done_does_not_transition(
        self, qualify_gate_service, mock_github, mock_store
    ):
        """Flow already in done state should NOT transition (terminal state)."""
        from vibe3.models.pr import PRResponse, PRState

        # Mock flow state already done
        mock_store.get_flow_state.return_value = {
            "branch": "task/my-feature",
            "flow_slug": "my_feature",
            "flow_status": "done",
            "executor_status": "running",
        }

        # Mock open PR
        open_pr = PRResponse(
            number=42,
            title="Test PR",
            state=PRState.OPEN,
            head_branch="task/my-feature",
            base_branch="main",
            url="https://github.com/test/pr/42",
            draft=False,
            is_ready=True,
            ci_passed=True,
        )
        mock_github.list_prs_for_branch.return_value = [open_pr]

        with patch("vibe3.domain.qualify_gate.FlowStatusService") as flow_status_cls:
            flow_status = MagicMock()
            flow_status_cls.return_value = flow_status

            result = qualify_gate_service.run_qualify_gate(
                issue=IssueInfo(
                    number=123,
                    title="Test Issue",
                    state=IssueState.IN_PROGRESS,
                    labels=["state/in-progress"],
                    assignees=["alice"],
                ),
                branch="task/my-feature",
                flow_state=mock_store.get_flow_state.return_value,
                labels=["state/in-progress"],
                trigger_state=IssueState.IN_PROGRESS,
            )

            # Should return trigger state (terminal state)
            assert result == IssueState.IN_PROGRESS
            # Should NOT call mark_flow_status
            flow_status.mark_flow_status.assert_not_called()

    def test_open_pr_no_pr_does_not_transition(
        self, qualify_gate_service, mock_github, mock_store
    ):
        """Active flow without PR should NOT transition."""
        # Mock flow state with running planner
        mock_store.get_flow_state.return_value = {
            "branch": "task/my-feature",
            "flow_slug": "my_feature",
            "flow_status": "active",
            "planner_status": "running",
        }

        # Mock no PR
        mock_github.list_prs_for_branch.return_value = []

        result = qualify_gate_service.run_qualify_gate(
            issue=IssueInfo(
                number=123,
                title="Test Issue",
                state=IssueState.IN_PROGRESS,
                labels=["state/in-progress"],
                assignees=["alice"],
            ),
            branch="task/my-feature",
            flow_state=mock_store.get_flow_state.return_value,
            labels=["state/in-progress"],
            trigger_state=IssueState.IN_PROGRESS,
        )

        # Should return trigger state (no PR)
        assert result == IssueState.IN_PROGRESS
