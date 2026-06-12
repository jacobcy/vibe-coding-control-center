"""Tests for multi-dependency blocked state handling."""

from unittest.mock import MagicMock, patch

from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.domain.qualify_gate import QualifyGateService
from vibe3.models import CoordinationTruth, IssueInfo, IssueState, OrchestraConfig
from vibe3.models.data_source import DataSource


def test_multi_dep_all_satisfied_unblocks():
    """Test that blocked issue unblocks when ALL dependencies are satisfied."""
    config = OrchestraConfig(repo="test/repo", main_branch="main")
    github = MagicMock()
    store = MagicMock(spec=SQLiteClient)
    flow_manager = MagicMock()

    service = QualifyGateService(
        config=config,
        github=github,
        store=store,
        flow_manager=flow_manager,
    )

    # Mock dependency checks: both #100 and #200 are closed
    service._is_dependency_satisfied = MagicMock(side_effect=lambda dep: True)

    issue = IssueInfo(
        number=300,
        title="Test issue",
        labels=["state/blocked"],
        github_state="open",
    )

    truth = CoordinationTruth(
        projection_state="blocked",
        projection_state_source=DataSource.ISSUE_BODY_FALLBACK,
        blocked_by_issues=[100, 200],
        blocked_by_issue_source=DataSource.ISSUE_BODY_FALLBACK,
    )

    # Mock flow_manager to return a branch
    flow_manager.get_flow_for_issue.return_value = {"branch": "task/issue-300"}

    # Mock coordination resolver
    with patch.object(
        service._coordination_resolver, "resolve_coordination", return_value=truth
    ):
        # Mock unblock service
        with patch(
            "vibe3.domain.qualify_gate.BlockedStateService"
        ) as mock_blocked_service:
            mock_result = MagicMock()
            mock_result.label_cleared = True
            mock_blocked_service.return_value.unblock.return_value = mock_result

            result = service.qualify_blocked_issue(issue)

            # Should unblock because all dependencies are satisfied
            assert result is not None
            assert result != IssueState.BLOCKED


def test_multi_dep_partial_satisfaction_remains_blocked():
    """Test that blocked issue remains blocked when only SOME dependencies satisfied."""
    config = OrchestraConfig(repo="test/repo", main_branch="main")
    github = MagicMock()
    store = MagicMock(spec=SQLiteClient)
    flow_manager = MagicMock()

    service = QualifyGateService(
        config=config,
        github=github,
        store=store,
        flow_manager=flow_manager,
    )

    # Mock dependency checks: #100 closed, #200 still open
    service._is_dependency_satisfied = MagicMock(
        side_effect=lambda dep: dep == 100  # Only #100 is satisfied
    )

    flow_manager.get_flow_for_issue.return_value = {"branch": "task/issue-300"}

    issue = IssueInfo(
        number=300,
        title="Test issue",
        labels=["state/blocked"],
        github_state="open",
    )

    truth = CoordinationTruth(
        projection_state="blocked",
        projection_state_source=DataSource.ISSUE_BODY_FALLBACK,
        blocked_by_issues=[100, 200],
        blocked_by_issue_source=DataSource.ISSUE_BODY_FALLBACK,
    )

    # Mock coordination resolver to return our truth
    with patch.object(
        service._coordination_resolver, "resolve_coordination", return_value=truth
    ):
        result = service.qualify_blocked_issue(issue)

        # Should remain blocked because #200 is still open
        assert result is None


def test_single_dep_satisfied_unblocks_backward_compat():
    """Test that single dependency case still works (backward compatibility)."""
    config = OrchestraConfig(repo="test/repo", main_branch="main")
    github = MagicMock()
    store = MagicMock(spec=SQLiteClient)
    flow_manager = MagicMock()

    service = QualifyGateService(
        config=config,
        github=github,
        store=store,
        flow_manager=flow_manager,
    )

    # Mock dependency check: #100 is closed
    service._is_dependency_satisfied = MagicMock(return_value=True)

    issue = IssueInfo(
        number=300,
        title="Test issue",
        labels=["state/blocked"],
        github_state="open",
    )

    truth = CoordinationTruth(
        projection_state="blocked",
        projection_state_source=DataSource.ISSUE_BODY_FALLBACK,
        blocked_by_issues=[100],
        blocked_by_issue_source=DataSource.ISSUE_BODY_FALLBACK,
    )

    # Mock flow_manager to return a branch
    flow_manager.get_flow_for_issue.return_value = {"branch": "task/issue-300"}

    # Mock coordination resolver
    with patch.object(
        service._coordination_resolver, "resolve_coordination", return_value=truth
    ):
        # Mock unblock service
        with patch(
            "vibe3.domain.qualify_gate.BlockedStateService"
        ) as mock_blocked_service:
            mock_result = MagicMock()
            mock_result.label_cleared = True
            mock_blocked_service.return_value.unblock.return_value = mock_result

            result = service.qualify_blocked_issue(issue)

            # Should unblock (single dependency regression test)
            assert result is not None
            assert result != IssueState.BLOCKED


def test_blocked_by_issue_computed_property_single():
    """Test that blocked_by_issue computed property returns first element."""
    truth = CoordinationTruth(
        blocked_by_issues=[100],
        blocked_by_issue_source=DataSource.ISSUE_BODY_FALLBACK,
    )

    # Computed property should return first element
    assert truth.blocked_by_issue == 100
    assert truth.is_blocked is True


def test_blocked_by_issue_computed_property_multiple():
    """Test that blocked_by_issue computed property returns first element of list."""
    truth = CoordinationTruth(
        blocked_by_issues=[100, 200, 300],
        blocked_by_issue_source=DataSource.ISSUE_BODY_FALLBACK,
    )

    # Computed property should return first element
    assert truth.blocked_by_issue == 100
    assert truth.is_blocked is True


def test_blocked_by_issue_computed_property_empty():
    """Test that blocked_by_issue computed property returns None when empty."""
    truth = CoordinationTruth(
        blocked_by_issues=[],
    )

    # Computed property should return None
    assert truth.blocked_by_issue is None
    assert truth.is_blocked is False
