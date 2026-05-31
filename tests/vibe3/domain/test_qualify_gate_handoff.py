"""Tests for QualifyGateService.qualify_handoff_issue method.

Covers the HANDOFF qualify gate check added to prevent erroneous manager
dispatch after reviewer completes with verdict PASS.
"""

from unittest.mock import Mock

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
    store.soft_delete_flow = Mock()
    return store


@pytest.fixture
def mock_flow_manager():
    return Mock()


@pytest.fixture
def qualify_gate_service(mock_config, mock_github, mock_store, mock_flow_manager):
    return QualifyGateService(
        config=mock_config,
        github=mock_github,
        store=mock_store,
        flow_manager=mock_flow_manager,
    )


@pytest.fixture
def handoff_issue():
    return IssueInfo(
        number=1678,
        title="Test HANDOFF Issue",
        state=IssueState.HANDOFF,
        labels=["state/handoff"],
        assignees=["manager-bot"],
    )


class TestQualifyHandoffIssue:
    """Tests for qualify_handoff_issue method."""

    def test_no_flow_returns_none(
        self, qualify_gate_service, handoff_issue, mock_flow_manager
    ):
        """HANDOFF issue without local flow should be skipped."""
        mock_flow_manager.get_flow_for_issue.return_value = None

        result = qualify_gate_service.qualify_handoff_issue(handoff_issue)

        assert result is None

    def test_verdict_present_returns_none(
        self, qualify_gate_service, handoff_issue, mock_flow_manager
    ):
        """HANDOFF issue with latest_verdict set should be skipped.

        After reviewer completes (verdict PASS), flow enters HANDOFF.
        The next heartbeat must NOT re-dispatch manager.
        """
        mock_flow_manager.get_flow_for_issue.return_value = {
            "branch": "task/issue-1678",
            "latest_verdict": {"value": "PASS", "role": "reviewer"},
            "pr_ref": None,
        }

        result = qualify_gate_service.qualify_handoff_issue(handoff_issue)

        assert result is None

    def test_pr_ref_present_returns_none(
        self, qualify_gate_service, handoff_issue, mock_flow_manager
    ):
        """HANDOFF issue with pr_ref should be skipped (PR awaiting merge)."""
        mock_flow_manager.get_flow_for_issue.return_value = {
            "branch": "task/issue-1678",
            "latest_verdict": None,
            "pr_ref": "https://github.com/test/repo/pull/42",
        }

        result = qualify_gate_service.qualify_handoff_issue(handoff_issue)

        assert result is None

    def test_no_verdict_no_pr_returns_handoff(
        self, qualify_gate_service, handoff_issue, mock_flow_manager
    ):
        """HANDOFF issue with no verdict and no pr_ref should dispatch manager."""
        mock_flow_manager.get_flow_for_issue.return_value = {
            "branch": "task/issue-1678",
            "latest_verdict": None,
            "pr_ref": None,
        }

        result = qualify_gate_service.qualify_handoff_issue(handoff_issue)

        assert result == IssueState.HANDOFF

    def test_empty_branch_returns_none(
        self, qualify_gate_service, handoff_issue, mock_flow_manager
    ):
        """HANDOFF issue with empty branch in flow should be skipped."""
        mock_flow_manager.get_flow_for_issue.return_value = {
            "branch": "",
            "latest_verdict": None,
            "pr_ref": None,
        }

        result = qualify_gate_service.qualify_handoff_issue(handoff_issue)

        assert result is None
