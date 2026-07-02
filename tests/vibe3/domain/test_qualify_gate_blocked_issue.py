"""Tests for QualifyGateService blocked issue dispatch qualification."""

from unittest.mock import Mock, patch

import pytest

from vibe3.domain.qualify_gate import QualifyGateService
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.models.orchestration import IssueInfo, IssueState
from vibe3.services.flow.blocked_state_types import (
    AutoResumeDecision,
    AutoResumeReasonCode,
    AutoResumeVerdict,
    ResumeResult,
)


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
    """Blocked issue should be qualified successfully via auto-resume."""
    mock_flow_manager.get_flow_for_issue.return_value = {
        "branch": "task/issue-123-test"
    }
    decision = AutoResumeDecision(
        verdict=AutoResumeVerdict.ELIGIBLE,
        reason_code=AutoResumeReasonCode.ELIGIBLE,
        issue_number=123,
        branch="task/issue-123-test",
        truth_snapshot="ts",
    )
    with patch("vibe3.domain.qualify_gate.BlockedStateService") as mock_bss:
        mock_bss.return_value.evaluate_auto_eligibility.return_value = decision
        mock_bss.return_value.apply_auto_resume.return_value = ResumeResult(
            success=True, target_state=IssueState.READY
        )
        result = qualify_gate_service.qualify_blocked_issue(sample_issue)

    assert result == IssueState.READY
    mock_bss.return_value.evaluate_auto_eligibility.assert_called_once_with(
        issue_number=123,
        branch="task/issue-123-test",
    )


def test_qualify_blocked_issue_stays_blocked_when_blocked(
    qualify_gate_service, sample_issue, mock_flow_manager
):
    """qualify_blocked_issue returns None when auto-resume is not eligible."""
    mock_flow_manager.get_flow_for_issue.return_value = {
        "branch": "task/issue-123-test"
    }
    decision = AutoResumeDecision(
        verdict=AutoResumeVerdict.NOT_ELIGIBLE,
        reason_code=AutoResumeReasonCode.DEPENDENCY_OPEN,
        issue_number=123,
        branch="task/issue-123-test",
        truth_snapshot="ts",
    )
    with patch("vibe3.domain.qualify_gate.BlockedStateService") as mock_bss:
        mock_bss.return_value.evaluate_auto_eligibility.return_value = decision
        result = qualify_gate_service.qualify_blocked_issue(sample_issue)

    assert result is None
    mock_bss.return_value.apply_auto_resume.assert_not_called()
