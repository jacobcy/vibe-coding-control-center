"""Tests for QualifyGateService blocked issue dispatch qualification."""

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
    qualify_gate_service, sample_issue, mock_flow_manager
):
    """Blocked issue should be qualified successfully via reconcile_blocked."""
    from unittest.mock import patch

    mock_flow_manager.get_flow_for_issue.return_value = {
        "branch": "task/issue-123-test"
    }
    with patch(
        "vibe3.domain.qualify_gate.BlockedStateService.reconcile_blocked",
        return_value=IssueState.READY,
    ) as mock_reconcile:
        result = qualify_gate_service.qualify_blocked_issue(sample_issue)

    assert result == IssueState.READY
    mock_reconcile.assert_called_once_with(
        issue_number=123,
        branch="task/issue-123-test",
        clear_reason=False,
        actor="orchestra:dispatcher",
    )


def test_qualify_blocked_issue_stays_blocked_when_blocked(
    qualify_gate_service, sample_issue, mock_flow_manager
):
    """qualify_blocked_issue returns None when reconcile_blocked returns None."""
    from unittest.mock import patch

    mock_flow_manager.get_flow_for_issue.return_value = {
        "branch": "task/issue-123-test"
    }
    with patch(
        "vibe3.domain.qualify_gate.BlockedStateService.reconcile_blocked",
        return_value=None,
    ) as mock_reconcile:
        result = qualify_gate_service.qualify_blocked_issue(sample_issue)

    assert result is None
    mock_reconcile.assert_called_once_with(
        issue_number=123,
        branch="task/issue-123-test",
        clear_reason=False,
        actor="orchestra:dispatcher",
    )
