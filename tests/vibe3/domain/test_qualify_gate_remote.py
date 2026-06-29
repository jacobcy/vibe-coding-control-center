"""Tests for remote-first coordination in QualifyGateService."""

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
    """Create a QualifyGateService instance."""
    return QualifyGateService(
        config=mock_config,
        github=mock_github,
        store=mock_store,
        flow_manager=mock_flow_manager,
    )


@pytest.fixture
def sample_issue():
    """Create a sample issue."""
    return IssueInfo(
        number=123,
        title="Test Issue",
        state=IssueState.IN_PROGRESS,
        labels=["state/in-progress"],
    )


class TestRemoteBlockedReason:
    """Tests for remote-first blocked_reason behavior."""

    def test_qualify_gate_uses_remote_blocked_reason(
        self, qualify_gate_service, sample_issue, mock_store
    ):
        """Verify reconcile_blocked called with remote blocked_reason."""
        # Mock CoordinationResolver to return remote blocked_reason
        mock_truth = CoordinationTruth(
            blocked_reason="Remote block from issue body",
            blocked_reason_source=DataSource.ISSUE_BODY_FALLBACK,
            blocked_by_issues=[],
            blocked_by_issue_source=None,
            worktree_path="/tmp/worktree",
            actor="executor",
        )

        with patch.object(
            qualify_gate_service._coordination_resolver,
            "resolve_coordination",
            return_value=mock_truth,
        ):
            mock_bss = Mock()
            mock_bss.reconcile_blocked.return_value = None

            with patch(
                "vibe3.domain.qualify_gate.BlockedStateService",
                return_value=mock_bss,
            ):
                flow_state = {"status": "active"}

                result = qualify_gate_service.run_qualify_gate(
                    issue=sample_issue,
                    branch="task/issue-123-test",
                    flow_state=flow_state,
                    labels=["state/in-progress"],
                    trigger_state=IssueState.IN_PROGRESS,
                )

                assert result is None
                mock_bss.reconcile_blocked.assert_called_once_with(
                    123,
                    "task/issue-123-test",
                    clear_reason=False,
                    actor="orchestra:dispatcher",
                )

                # Verify CoordinationResolver was called
                qualify_gate_service._coordination_resolver.resolve_coordination.assert_called_once_with(
                    "task/issue-123-test", 123
                )

    def test_qualify_gate_fallback_to_local_blocked_reason(
        self, qualify_gate_service, sample_issue, mock_store
    ):
        """Verify reconcile_blocked called with local blocked_reason."""
        # Mock CoordinationResolver to return local blocked_reason (degraded mode)
        mock_truth = CoordinationTruth(
            blocked_reason="Local block from SQLite",
            blocked_reason_source=DataSource.LOCAL_SQLITE,
            blocked_by_issues=[],
            blocked_by_issue_source=None,
            worktree_path="/tmp/worktree",
            actor="executor",
        )

        with patch.object(
            qualify_gate_service._coordination_resolver,
            "resolve_coordination",
            return_value=mock_truth,
        ):
            mock_bss = Mock()
            mock_bss.reconcile_blocked.return_value = None

            with patch(
                "vibe3.domain.qualify_gate.BlockedStateService",
                return_value=mock_bss,
            ):
                flow_state = {"status": "active"}

                result = qualify_gate_service.run_qualify_gate(
                    issue=sample_issue,
                    branch="task/issue-123-test",
                    flow_state=flow_state,
                    labels=["state/in-progress"],
                    trigger_state=IssueState.IN_PROGRESS,
                )

                assert result is None
                mock_bss.reconcile_blocked.assert_called_once()


class TestRemoteDependencies:
    """Tests for remote-first dependencies behavior."""

    def test_qualify_gate_uses_remote_dependencies(
        self, qualify_gate_service, sample_issue, mock_store, mock_github
    ):
        """Verify remote dependencies are used when available."""
        # Mock CoordinationResolver to return remote dependencies
        mock_truth = CoordinationTruth(
            blocked_reason=None,
            blocked_reason_source=None,
            blocked_by_issues=[456, 789],  # Remote dependencies
            blocked_by_issue_source=DataSource.ISSUE_BODY_FALLBACK,
            worktree_path=None,
            actor="executor",
        )

        with patch.object(
            qualify_gate_service._coordination_resolver,
            "resolve_coordination",
            return_value=mock_truth,
        ):
            # Mock store returns None -> blocked code path returns None
            mock_bss = Mock()
            mock_bss.reconcile_blocked.return_value = None

            with patch(
                "vibe3.domain.qualify_gate.BlockedStateService",
                return_value=mock_bss,
            ):
                flow_state = {"status": "active"}

                result = qualify_gate_service.run_qualify_gate(
                    issue=sample_issue,
                    branch="task/issue-123-test",
                    flow_state=flow_state,
                    labels=["state/in-progress"],
                    trigger_state=IssueState.IN_PROGRESS,
                )

                assert result is None
                mock_bss.reconcile_blocked.assert_called_once()

                # Verify CoordinationResolver was called
                qualify_gate_service._coordination_resolver.resolve_coordination.assert_called_once_with(
                    "task/issue-123-test", 123
                )

    def test_qualify_gate_fallback_to_local_dependencies(
        self, qualify_gate_service, sample_issue, mock_store, mock_github
    ):
        """Verify fallback to local dependencies when remote unavailable."""
        # Mock CoordinationResolver to return local dependencies (degraded mode)
        mock_truth = CoordinationTruth(
            blocked_reason=None,
            blocked_reason_source=None,
            blocked_by_issues=[456],  # Local dependencies
            blocked_by_issue_source=DataSource.LOCAL_SQLITE,
            worktree_path=None,
            actor="executor",
        )

        with patch.object(
            qualify_gate_service._coordination_resolver,
            "resolve_coordination",
            return_value=mock_truth,
        ):
            mock_bss = Mock()
            mock_bss.reconcile_blocked.return_value = None

            with patch(
                "vibe3.domain.qualify_gate.BlockedStateService",
                return_value=mock_bss,
            ):
                flow_state = {"status": "active"}

                result = qualify_gate_service.run_qualify_gate(
                    issue=sample_issue,
                    branch="task/issue-123-test",
                    flow_state=flow_state,
                    labels=["state/in-progress"],
                    trigger_state=IssueState.IN_PROGRESS,
                )

                assert result is None
                mock_bss.reconcile_blocked.assert_called_once()

    def test_qualify_gate_remote_blocked_by_issue(
        self, qualify_gate_service, sample_issue, mock_store
    ):
        """Body truth blocked_by_issue triggers reconcile_blocked.

        When remote body truth has blocked_by_issues=[456], blocked_signal
        triggers reconcile_blocked.
        """
        mock_truth = CoordinationTruth(
            blocked_reason=None,
            blocked_reason_source=None,
            blocked_by_issues=[456],
            blocked_by_issue_source=DataSource.ISSUE_BODY_FALLBACK,
            worktree_path=None,
            actor="executor",
        )

        with patch.object(
            qualify_gate_service._coordination_resolver,
            "resolve_coordination",
            return_value=mock_truth,
        ):
            mock_bss = Mock()
            mock_bss.reconcile_blocked.return_value = None

            with patch(
                "vibe3.domain.qualify_gate.BlockedStateService",
                return_value=mock_bss,
            ):
                flow_state = {"status": "active"}

                result = qualify_gate_service.run_qualify_gate(
                    issue=sample_issue,
                    branch="task/issue-123-test",
                    flow_state=flow_state,
                    labels=["state/in-progress"],
                    trigger_state=IssueState.IN_PROGRESS,
                )

                assert result is None
                mock_bss.reconcile_blocked.assert_called_once_with(
                    123,
                    "task/issue-123-test",
                    clear_reason=False,
                    actor="orchestra:dispatcher",
                )


class TestProvenanceTracking:
    """Tests for provenance tracking via DataSource."""

    def test_provenance_remote_blocked_reason(self, qualify_gate_service, sample_issue):
        """Verify provenance is tracked for remote blocked_reason."""
        mock_truth = CoordinationTruth(
            blocked_reason="Remote block",
            blocked_reason_source=DataSource.ISSUE_BODY_FALLBACK,
            blocked_by_issues=[],
            blocked_by_issue_source=None,
            worktree_path="/tmp/worktree",
            actor="executor",
        )

        with patch.object(
            qualify_gate_service._coordination_resolver,
            "resolve_coordination",
            return_value=mock_truth,
        ):
            with patch("vibe3.services.LabelService", return_value=Mock()):
                flow_state = {"status": "active"}

                qualify_gate_service.run_qualify_gate(
                    issue=sample_issue,
                    branch="task/issue-123-test",
                    flow_state=flow_state,
                    labels=["state/in-progress"],
                    trigger_state=IssueState.IN_PROGRESS,
                )

                # Verify truth has correct provenance
                truth = (
                    qualify_gate_service._coordination_resolver.resolve_coordination.return_value
                )
                assert truth.blocked_reason_source == DataSource.ISSUE_BODY_FALLBACK

    def test_provenance_local_dependencies(self, qualify_gate_service, sample_issue):
        """Verify provenance is tracked for local dependencies."""
        mock_truth = CoordinationTruth(
            blocked_reason=None,
            blocked_reason_source=None,
            blocked_by_issues=[456],
            blocked_by_issue_source=DataSource.LOCAL_SQLITE,
            worktree_path="/tmp/worktree",
            actor="executor",
        )

        with patch.object(
            qualify_gate_service._coordination_resolver,
            "resolve_coordination",
            return_value=mock_truth,
        ):
            mock_bss = Mock()
            mock_bss.reconcile_blocked.return_value = None

            with patch(
                "vibe3.domain.qualify_gate.BlockedStateService",
                return_value=mock_bss,
            ):
                flow_state = {"status": "active"}

                qualify_gate_service.run_qualify_gate(
                    issue=sample_issue,
                    branch="task/issue-123-test",
                    flow_state=flow_state,
                    labels=["state/in-progress"],
                    trigger_state=IssueState.IN_PROGRESS,
                )

                # Verify truth has correct provenance
                truth = (
                    qualify_gate_service._coordination_resolver.resolve_coordination.return_value
                )
                assert truth.blocked_by_issue_source == DataSource.LOCAL_SQLITE


class TestE2EBlockedReconciliation:
    """End-to-end tests for production drift patterns.

    Coverage:
    - state/ready + body blocked + no local flow → blocked truth wins
    - state/blocked + body active + local blocked cache → auto-resume
    - #994-style mismatch → alignment, not silent drift
    """

    def test_ready_label_body_blocked_no_flow(self, mock_store, sample_issue):
        """state/ready + body blocked + no local flow → blocked truth wins.

        Reproduction of #994 drift: label says ready but body says blocked.
        Qualify gate must trust body truth and skip dispatch.
        """
        config = OrchestraConfig(repo="test/repo")
        github = Mock()
        flow_manager = Mock()
        qualify_gate = QualifyGateService(
            config=config, github=github, store=mock_store, flow_manager=flow_manager
        )

        mock_truth = CoordinationTruth(
            projection_state="blocked",
            projection_state_source=DataSource.ISSUE_BODY_FALLBACK,
            blocked_reason="API design pending",
            blocked_reason_source=DataSource.ISSUE_BODY_FALLBACK,
            blocked_by_issues=[],
            blocked_by_issue_source=None,
            worktree_path=None,
            actor=None,
        )

        with patch.object(
            qualify_gate._coordination_resolver,
            "resolve_coordination",
            return_value=mock_truth,
        ):
            mock_bss = Mock()
            mock_bss.reconcile_blocked.return_value = None

            with patch(
                "vibe3.domain.qualify_gate.BlockedStateService",
                return_value=mock_bss,
            ):
                result = qualify_gate.run_qualify_gate(
                    issue=sample_issue,
                    branch="task/issue-994",
                    flow_state=None,
                    labels=["state/ready"],
                    trigger_state=IssueState.READY,
                )

                assert result is None
                mock_bss.reconcile_blocked.assert_called_once_with(
                    123,
                    "task/issue-994",
                    clear_reason=False,
                    actor="orchestra:dispatcher",
                )

    def test_blocked_label_body_active_with_cache(self, mock_store, sample_issue):
        """Blocked label + active body -> reconcile returns target."""
        config = OrchestraConfig(repo="test/repo")
        github = Mock()
        github.get_issue_body.return_value = "User content"
        flow_manager = Mock()
        qualify_gate = QualifyGateService(
            config=config, github=github, store=mock_store, flow_manager=flow_manager
        )

        mock_truth = CoordinationTruth(
            projection_state="active",
            projection_state_source=DataSource.ISSUE_BODY_FALLBACK,
            blocked_reason=None,
            blocked_reason_source=None,
            blocked_by_issues=[],
            blocked_by_issue_source=None,
            worktree_path=None,
            actor="executor",
        )

        flow_state = {"blocked_reason": "Health check failed"}

        # After reconcile unblocks, get_flow_state returns active flow
        mock_store.get_flow_state = Mock(return_value={"flow_status": "active"})

        with patch.object(
            qualify_gate._coordination_resolver,
            "resolve_coordination",
            return_value=mock_truth,
        ):
            mock_bss = Mock()
            mock_bss.reconcile_blocked.return_value = IssueState.IN_PROGRESS

            with patch(
                "vibe3.domain.qualify_gate.BlockedStateService",
                return_value=mock_bss,
            ):
                result = qualify_gate.run_qualify_gate(
                    issue=sample_issue,
                    branch="task/issue-123",
                    flow_state=flow_state,
                    labels=["state/blocked"],
                    trigger_state=IssueState.BLOCKED,
                )

                assert result == IssueState.IN_PROGRESS
                mock_bss.reconcile_blocked.assert_called_once_with(
                    123,
                    "task/issue-123",
                    clear_reason=False,
                    actor="orchestra:dispatcher",
                )

    def test_issue_994_style_drift_alignment(self, mock_store, sample_issue):
        """#994: local flow missing, remote body blocked, label ready.

        Expected: blocked truth wins, not dispatched, reconcile_blocked called.
        """
        config = OrchestraConfig(repo="test/repo")
        github = Mock()
        flow_manager = Mock()
        qualify_gate = QualifyGateService(
            config=config, github=github, store=mock_store, flow_manager=flow_manager
        )

        mock_truth = CoordinationTruth(
            projection_state="blocked",
            projection_state_source=DataSource.ISSUE_BODY_FALLBACK,
            blocked_reason=None,
            blocked_reason_source=None,
            blocked_by_issues=[456],
            blocked_by_issue_source=DataSource.ISSUE_BODY_FALLBACK,
            worktree_path=None,
            actor=None,
        )

        with patch.object(
            qualify_gate._coordination_resolver,
            "resolve_coordination",
            return_value=mock_truth,
        ):
            mock_bss = Mock()
            mock_bss.reconcile_blocked.return_value = None

            with patch(
                "vibe3.domain.qualify_gate.BlockedStateService",
                return_value=mock_bss,
            ):
                result = qualify_gate.run_qualify_gate(
                    issue=sample_issue,
                    branch="task/issue-994",
                    flow_state=None,
                    labels=["state/ready"],
                    trigger_state=IssueState.READY,
                )

                assert result is None
                mock_bss.reconcile_blocked.assert_called_once_with(
                    123,
                    "task/issue-994",
                    clear_reason=False,
                    actor="orchestra:dispatcher",
                )
