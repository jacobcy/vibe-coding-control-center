"""Tests for multi-dependency blocked state handling."""

from unittest.mock import MagicMock, patch

from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.domain.qualify_gate import QualifyGateService
from vibe3.models import CoordinationTruth, IssueInfo, IssueState, OrchestraConfig
from vibe3.models.data_source import DataSource
from vibe3.services.flow.blocked_state_types import (
    AutoResumeDecision,
    AutoResumeReasonCode,
    AutoResumeVerdict,
    ResumeResult,
)


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

    decision = AutoResumeDecision(
        verdict=AutoResumeVerdict.ELIGIBLE,
        reason_code=AutoResumeReasonCode.ELIGIBLE,
        issue_number=300,
        branch="task/issue-300",
        truth_snapshot="ts",
    )

    # Mock coordination resolver
    with patch.object(
        service._coordination_resolver, "resolve_coordination", return_value=truth
    ):
        # Mock BlockedStateService to simulate full unblock
        with patch(
            "vibe3.domain.qualify_gate.BlockedStateService"
        ) as mock_blocked_service:
            mock_blocked_service.return_value.evaluate_auto_eligibility.return_value = (
                decision
            )
            mock_blocked_service.return_value.apply_auto_resume.return_value = (
                ResumeResult(success=True, target_state=IssueState.IN_PROGRESS)
            )

            result = service.qualify_blocked_issue(issue)

            # Should unblock because all dependencies are satisfied
            assert result is not None
            assert result != IssueState.BLOCKED
            mock_blocked_service.return_value.evaluate_auto_eligibility.assert_called_once_with(
                issue_number=300,
                branch="task/issue-300",
            )


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

    decision = AutoResumeDecision(
        verdict=AutoResumeVerdict.NOT_ELIGIBLE,
        reason_code=AutoResumeReasonCode.DEPENDENCY_OPEN,
        issue_number=300,
        branch="task/issue-300",
        truth_snapshot="ts",
    )

    # Mock coordination resolver to return our truth
    with patch.object(
        service._coordination_resolver, "resolve_coordination", return_value=truth
    ):
        # Mock BlockedStateService to simulate still blocked
        with patch(
            "vibe3.domain.qualify_gate.BlockedStateService"
        ) as mock_blocked_service:
            mock_blocked_service.return_value.evaluate_auto_eligibility.return_value = (
                decision
            )

            result = service.qualify_blocked_issue(issue)

            # Should remain blocked (not eligible)
            assert result is None
            mock_blocked_service.return_value.apply_auto_resume.assert_not_called()


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

    decision = AutoResumeDecision(
        verdict=AutoResumeVerdict.ELIGIBLE,
        reason_code=AutoResumeReasonCode.ELIGIBLE,
        issue_number=300,
        branch="task/issue-300",
        truth_snapshot="ts",
    )

    # Mock coordination resolver
    with patch.object(
        service._coordination_resolver, "resolve_coordination", return_value=truth
    ):
        # Mock BlockedStateService to simulate unblock
        with patch(
            "vibe3.domain.qualify_gate.BlockedStateService"
        ) as mock_blocked_service:
            mock_blocked_service.return_value.evaluate_auto_eligibility.return_value = (
                decision
            )
            mock_blocked_service.return_value.apply_auto_resume.return_value = (
                ResumeResult(success=True, target_state=IssueState.IN_PROGRESS)
            )

            result = service.qualify_blocked_issue(issue)

            # Should unblock (single dependency regression test)
            assert result is not None
            assert result != IssueState.BLOCKED
            mock_blocked_service.return_value.evaluate_auto_eligibility.assert_called_once_with(
                issue_number=300,
                branch="task/issue-300",
            )


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
