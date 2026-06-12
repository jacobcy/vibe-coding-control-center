"""Tests for QualifyGateService blocked issue dispatch qualification."""

from unittest.mock import Mock, patch

import pytest

from vibe3.domain.qualify_gate import QualifyGateService
from vibe3.models.coordination_truth import CoordinationTruth
from vibe3.models.data_source import DataSource
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


def test_qualify_blocked_issue_no_branch(
    qualify_gate_service, sample_issue, mock_flow_manager
):
    """Issue with no branch should return None."""
    mock_flow_manager.get_flow_for_issue.return_value = None

    result = qualify_gate_service.qualify_blocked_issue(sample_issue)

    assert result is None


def test_qualify_blocked_issue_success(
    qualify_gate_service, sample_issue, mock_flow_manager, mock_store
):
    """Blocked issue should be qualified successfully."""
    mock_flow_manager.get_flow_for_issue.return_value = {
        "branch": "task/issue-123-test"
    }
    mock_store.get_flow_state.return_value = {}
    qualify_gate_service.run_qualify_gate = Mock(return_value=IssueState.IN_PROGRESS)

    result = qualify_gate_service.qualify_blocked_issue(sample_issue)

    assert result == IssueState.IN_PROGRESS
    qualify_gate_service.run_qualify_gate.assert_called_once()


def test_qualify_blocked_issue_reuses_truth(
    qualify_gate_service, sample_issue, mock_flow_manager
):
    """qualify_blocked_issue checks deps and returns None if still blocked."""
    mock_flow_manager.get_flow_for_issue.return_value = {
        "branch": "task/issue-123-test"
    }
    mock_truth = CoordinationTruth(
        blocked_reason="Blocked by #456",
        blocked_reason_source=DataSource.ISSUE_BODY_FALLBACK,
        blocked_by_issues=[456],
        blocked_by_issue_source=DataSource.ISSUE_BODY_FALLBACK,
        dependencies=[],
        dependencies_source=None,
        worktree_path="/tmp/worktree",
        actor="executor",
    )
    with patch.object(
        qualify_gate_service._coordination_resolver,
        "resolve_coordination",
        return_value=mock_truth,
    ) as mock_resolve:
        qualify_gate_service._is_dependency_satisfied = Mock(return_value=False)

        result = qualify_gate_service.qualify_blocked_issue(sample_issue)

    mock_resolve.assert_called_once_with("task/issue-123-test", 123)
    # Should return None because dependency is still open
    assert result is None


def test_qualify_blocked_issue_resumes_when_dependency_closed(
    qualify_gate_service, sample_issue, mock_flow_manager, mock_store
):
    """Closed dependency should clear blocked state and become dispatchable."""
    mock_flow_manager.get_flow_for_issue.return_value = {"branch": "task/issue-123"}
    mock_store.get_flow_state.return_value = {
        "branch": "task/issue-123",
        "flow_slug": "issue-123",
        "flow_status": "blocked",
        "blocked_by_issue": 456,
    }
    mock_truth = CoordinationTruth(
        blocked_reason="Blocked by #456",
        blocked_reason_source=DataSource.ISSUE_BODY_FALLBACK,
        blocked_by_issues=[456],
        blocked_by_issue_source=DataSource.ISSUE_BODY_FALLBACK,
        dependencies=[],
        dependencies_source=None,
        worktree_path=None,
        actor="executor",
    )
    with patch.object(
        qualify_gate_service._coordination_resolver,
        "resolve_coordination",
        return_value=mock_truth,
    ):
        qualify_gate_service._is_dependency_satisfied = Mock(return_value=True)
        with patch("vibe3.domain.qualify_gate.BlockedStateService") as service_cls:
            service = service_cls.return_value
            service.unblock.return_value.label_cleared = True

            result = qualify_gate_service.qualify_blocked_issue(sample_issue)

    assert result == IssueState.READY
    service.unblock.assert_called_once()
    assert service.unblock.call_args.kwargs["branch"] == "task/issue-123"
    assert service.unblock.call_args.kwargs["issue_number"] == 123
