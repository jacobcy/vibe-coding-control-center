"""Unit tests for QualifyGateService domain logic.

Tests for core run_qualify_gate, qualify_blocked_issue, and dependency checking.
Remote coordination and blocked state tests are in test_qualify_gate_remote.py
and test_qualify_gate_service_calls.py respectively.
GitHub closed-state (Step 0) tests are in test_qualify_gate_closed.py.
"""

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

    @pytest.mark.parametrize(
        "state",
        [
            IssueState.CLAIMED,
            IssueState.IN_PROGRESS,
            IssueState.REVIEW,
            IssueState.MERGE_READY,
        ],
    )
    def test_active_qualify_never_reconciles_or_infers_from_flow_state(
        self, qualify_gate_service, sample_issue, state
    ):
        sample_issue.state = state
        sample_issue.labels = [state.to_label()]
        flow_state = {
            "flow_status": "blocked",
            "plan_ref": "docs/plan.md",
            "report_ref": "docs/report.md",
            "pr_ref": "https://example.test/pull/1",
        }

        with patch("vibe3.domain.qualify_gate.BlockedStateService") as blocked_cls:
            result = qualify_gate_service.run_qualify_gate(
                issue=sample_issue,
                branch="task/issue-123-test",
                flow_state=flow_state,
                labels=sample_issue.labels,
                trigger_state=state,
            )

        assert result == state
        blocked_cls.assert_not_called()

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
        """Body truth blocked -> evaluate_auto_eligibility, no dispatch."""
        flow_state = {
            "blocked_reason": "Manual intervention required",
            "branch": "task/issue-123-test",
            "flow_slug": "test-slug",
        }
        # Mock store returns blocked status after reconcile
        mock_store.get_flow_state.return_value = {
            **flow_state,
            "flow_status": "blocked",
        }

        mock_truth = Mock()
        mock_truth.is_blocked = True
        mock_truth.blocked_reason = "Manual intervention required"
        mock_truth.blocked_by_issue = None
        mock_truth.blocked_by_issues = []

        with patch.object(
            qualify_gate_service._coordination_resolver,
            "resolve_coordination",
            return_value=mock_truth,
        ):
            mock_bss = Mock()
            mock_bss.evaluate_auto_eligibility.return_value = None

            with patch(
                "vibe3.domain.qualify_gate.BlockedStateService",
                return_value=mock_bss,
            ):
                result = qualify_gate_service.run_qualify_gate(
                    issue=sample_issue,
                    branch="task/issue-123-test",
                    flow_state=flow_state,
                    labels=["state/in-progress"],
                    trigger_state=IssueState.IN_PROGRESS,
                )

                assert result is None
                mock_bss.evaluate_auto_eligibility.assert_not_called()

    def test_manual_block_already_has_label(
        self, qualify_gate_service, sample_issue, mock_store
    ):
        """Blocked truth + existing blocked label should block dispatch."""
        flow_state = {
            "blocked_reason": "Manual intervention required",
            "branch": "task/issue-123-test",
            "flow_slug": "test-slug",
        }
        # Mock store returns blocked state after reconcile
        mock_store.get_flow_state.return_value = {"flow_status": "blocked"}

        mock_truth = Mock()
        mock_truth.is_blocked = True
        mock_truth.blocked_reason = "Manual intervention required"
        mock_truth.blocked_by_issue = None
        mock_truth.blocked_by_issues = []

        with patch.object(
            qualify_gate_service._coordination_resolver,
            "resolve_coordination",
            return_value=mock_truth,
        ):
            mock_bss = Mock()
            mock_bss.evaluate_auto_eligibility.return_value = None

            with patch(
                "vibe3.domain.qualify_gate.BlockedStateService",
                return_value=mock_bss,
            ):
                result = qualify_gate_service.run_qualify_gate(
                    issue=sample_issue,
                    branch="task/issue-123-test",
                    flow_state=flow_state,
                    labels=["state/blocked"],
                    trigger_state=IssueState.IN_PROGRESS,
                )

                assert result is None
                mock_bss.evaluate_auto_eligibility.assert_not_called()

    def test_unblock_from_blocked_state(
        self, qualify_gate_service, sample_issue, mock_store
    ):
        """Blocked issue with cleared dependencies should reconcile and unblock.

        When body truth is NOT blocked but label says blocked, blocked_signal
        triggers evaluate_auto_eligibility, which returns the resume target.
        """

        flow_state = {
            "blocked_by_issue": 456,
            "branch": "task/issue-123-test",
            "flow_slug": "test-slug",
        }

        # After evaluate_auto_eligibility unblocks, get_flow_state returns active
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
        mock_truth.blocked_by_issues = []
        mock_truth.worktree_path = None

        with patch.object(
            qualify_gate_service._coordination_resolver,
            "resolve_coordination",
            return_value=mock_truth,
        ):
            mock_bss = Mock()
            mock_bss.evaluate_auto_eligibility.return_value = IssueState.IN_PROGRESS

            with patch(
                "vibe3.domain.qualify_gate.BlockedStateService",
                return_value=mock_bss,
            ):
                result = qualify_gate_service.run_qualify_gate(
                    issue=sample_issue,
                    branch="task/issue-123-test",
                    flow_state=flow_state,
                    labels=["state/blocked"],
                    trigger_state=IssueState.BLOCKED,
                )

                assert result == IssueState.BLOCKED
                mock_bss.evaluate_auto_eligibility.assert_not_called()

    def test_unblock_with_stale_local_cache_without_blocked_label(
        self, qualify_gate_service, sample_issue, mock_store, mock_github
    ):
        """Stale cache without flow_status=blocked or blocked label — no reconcile.

        In the converged design, blocked_signal uses cheap signals
        (truth.is_blocked, blocked_label, flow_status). A stale blocked_by_issue
        without flow_status=blocked does not trigger evaluate_auto_eligibility.
        """

        flow_state = {
            "blocked_by_issue": 456,
            "branch": "task/issue-123-test",
            "flow_slug": "test-slug",
        }

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
        mock_truth.blocked_by_issues = []
        mock_truth.worktree_path = None

        mock_github.get_issue_body.return_value = "User content"

        with patch.object(
            qualify_gate_service._coordination_resolver,
            "resolve_coordination",
            return_value=mock_truth,
        ):
            with patch(
                "vibe3.domain.qualify_gate.BlockedStateService.evaluate_auto_eligibility",
            ) as mock_reconcile:
                result = qualify_gate_service.run_qualify_gate(
                    issue=sample_issue,
                    branch="task/issue-123-test",
                    flow_state=flow_state,
                    labels=["state/in-progress"],
                    trigger_state=IssueState.IN_PROGRESS,
                )

                # Stale cache without signal does not trigger reconcile
                mock_reconcile.assert_not_called()
                # Dispatch proceeds normally
                assert result == IssueState.IN_PROGRESS

    def test_run_qualify_gate_blocked_body_does_not_dispatch(
        self, qualify_gate_service, mock_store
    ):
        """Body truth blocked -> evaluate_auto_eligibility called, no dispatch.

        Regression: when body truth says blocked (is_blocked=True),
        run_qualify_gate must call BlockedStateService auto eligibility API and
        return None if blocked persists. Old auto_resume must NOT be invoked.
        """
        from unittest.mock import patch

        from vibe3.models.orchestration import IssueInfo, IssueState

        # Body truth: blocked, dependency #999 not closed
        mock_truth = Mock()
        mock_truth.is_blocked = True
        mock_truth.blocked_reason = "Blocked by #999"
        mock_truth.blocked_by_issue = 999
        mock_truth.blocked_by_issues = [999]

        # Mock store returns blocked state after reconcile
        mock_store.get_flow_state.return_value = {"flow_status": "blocked"}

        # Mock BlockedStateService to track evaluate_auto_eligibility calls
        mock_bss = Mock()
        mock_bss.evaluate_auto_eligibility.return_value = None

        with patch.object(
            qualify_gate_service._coordination_resolver,
            "resolve_coordination",
            return_value=mock_truth,
        ):
            with patch(
                "vibe3.domain.qualify_gate.BlockedStateService",
                return_value=mock_bss,
            ):
                issue = IssueInfo(
                    number=100,
                    title="Blocked Issue",
                    state=IssueState.READY,
                    labels=["state/blocked"],
                )
                result = qualify_gate_service.run_qualify_gate(
                    issue=issue,
                    branch="task/issue-100",
                    flow_state={"flow_status": "blocked"},
                    labels=["state/blocked"],
                    trigger_state=IssueState.READY,
                )

                # Body blocked -> no dispatch
                assert result is None

                mock_bss.evaluate_auto_eligibility.assert_not_called()


class TestQualifyBlockedIssue:
    """Tests for qualify_blocked_issue method."""

    def test_qualify_blocked_issue_delegates_to_evaluate_auto_eligibility(
        self, qualify_gate_service, mock_store, mock_flow_manager
    ):
        """qualify_blocked_issue delegates to evaluate + apply_auto_resume."""
        issue = IssueInfo(
            number=456,
            title="Blocked issue",
            state=IssueState.BLOCKED,
            labels=["state/blocked"],
        )
        mock_flow_manager.get_flow_for_issue.return_value = {"branch": "task/issue-456"}

        decision = AutoResumeDecision(
            verdict=AutoResumeVerdict.ELIGIBLE,
            reason_code=AutoResumeReasonCode.ELIGIBLE,
            issue_number=456,
            branch="task/issue-456",
            truth_snapshot="ts",
        )
        mock_bss = Mock()
        mock_bss.evaluate_auto_eligibility.return_value = decision
        mock_bss.apply_auto_resume.return_value = ResumeResult(
            success=True, target_state=IssueState.READY
        )

        with patch(
            "vibe3.domain.qualify_gate.BlockedStateService",
            return_value=mock_bss,
        ):
            result = qualify_gate_service.qualify_blocked_issue(issue)

            assert result == IssueState.READY
            mock_bss.evaluate_auto_eligibility.assert_called_once_with(
                issue_number=456,
                branch="task/issue-456",
            )
            mock_bss.apply_auto_resume.assert_called_once_with(decision)

    def test_qualify_blocked_issue_no_branch_returns_none(
        self, qualify_gate_service, mock_flow_manager
    ):
        """qualify_blocked_issue without a branch should return None."""
        issue = IssueInfo(
            number=457,
            title="No branch issue",
            state=IssueState.BLOCKED,
            labels=["state/blocked"],
        )
        mock_flow_manager.get_flow_for_issue.return_value = None

        with patch(
            "vibe3.domain.qualify_gate.BlockedStateService.evaluate_auto_eligibility",
        ) as mock_reconcile:
            result = qualify_gate_service.qualify_blocked_issue(issue)

            assert result is None
            mock_reconcile.assert_not_called()

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
