"""Placeholder flow checks for QualifyGateService."""

from unittest.mock import MagicMock, Mock, patch

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
    github = Mock()
    github.get_issue_body = Mock(return_value="")
    return github


@pytest.fixture
def mock_store():
    """Create a mock SQLite client."""
    store = Mock()
    store.db_path = ":memory:"
    store.get_flow_state = Mock(return_value=None)
    return store


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


def test_check_worktree_health_skips_placeholder(
    mock_config, mock_github, mock_store, sample_issue
):
    """Placeholder flow (blocked + no worktree) skips worktree health check."""
    mock_store.get_flow_state.return_value = {
        "branch": "task/issue-123",
        "flow_status": "blocked",
        "blocked_reason": "Waiting for dependency",
    }
    service = QualifyGateService(
        config=mock_config,
        github=mock_github,
        store=mock_store,
        flow_manager=MagicMock(),
    )
    truth = CoordinationTruth(
        blocked_reason="Waiting for dependency",
        blocked_reason_source=DataSource.ISSUE_BODY_FALLBACK,
        blocked_by_issue=None,
        dependencies=[],
        worktree_path=None,
    )

    result = service._check_worktree_health(
        issue=sample_issue,
        branch="task/issue-123",
        truth=truth,
    )

    assert result is True


@pytest.mark.slow
def test_check_worktree_health_blocked_real_flow_checks_path(
    mock_config, mock_github, mock_store, sample_issue
):
    """Blocked flow with a worktree path should still check structural health."""
    mock_store.get_flow_state.return_value = {
        "branch": "task/issue-456",
        "flow_status": "blocked",
    }
    # set_block -> sync_block_state -> rebuild_cache_from_truth needs iterable deps
    mock_store.get_dependency_links.return_value = []
    service = QualifyGateService(
        config=mock_config,
        github=mock_github,
        store=mock_store,
        flow_manager=MagicMock(),
    )
    truth = CoordinationTruth(worktree_path="/tmp/worktree/task-issue-456")

    with (
        patch("vibe3.domain.qualify_gate.Path") as mock_path,
        patch("vibe3.services.LabelService") as mock_label_service_cls,
    ):
        mock_path.return_value.exists.return_value = False
        mock_label_service_cls.return_value.replace_issue_state.return_value = (
            "normalized"
        )

        result = service._check_worktree_health(
            issue=sample_issue,
            branch="task/issue-456",
            truth=truth,
        )

    assert result is False
    mock_path.assert_called_once_with("/tmp/worktree/task-issue-456")
    mock_label_service_cls.return_value.replace_issue_state.assert_not_called()
