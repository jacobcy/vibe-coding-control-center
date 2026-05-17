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
        assignees=["alice"],
    )


class TestRemoteBlockedReason:
    """Tests for remote-first blocked_reason behavior."""

    def test_qualify_gate_uses_remote_blocked_reason(
        self, qualify_gate_service, sample_issue, mock_store
    ):
        """Verify remote blocked_reason is used when available."""
        # Mock CoordinationResolver to return remote blocked_reason
        mock_truth = CoordinationTruth(
            blocked_reason="Remote block from issue body",
            blocked_reason_source=DataSource.ISSUE_BODY_FALLBACK,
            blocked_by_issue=None,
            blocked_by_issue_source=None,
            dependencies=[],
            dependencies_source=None,
            worktree_path="/tmp/worktree",
            actor="executor",
        )

        with patch.object(
            qualify_gate_service._coordination_resolver,
            "resolve_coordination",
            return_value=mock_truth,
        ):
            mock_label_port = Mock()
            with patch(
                "vibe3.domain.qualify_gate.GhIssueLabelPort",
                return_value=mock_label_port,
            ):
                # Use non-empty flow_state to avoid early return
                flow_state = {"status": "active"}

                result = qualify_gate_service.run_qualify_gate(
                    issue=sample_issue,
                    branch="task/issue-123-test",
                    flow_state=flow_state,
                    labels=["state/in-progress"],
                    trigger_state=IssueState.IN_PROGRESS,
                )

                # Verify blocked by remote reason
                assert result is None
                mock_label_port.add_issue_label.assert_called_once_with(
                    123, "state/blocked"
                )

                # Verify CoordinationResolver was called
                qualify_gate_service._coordination_resolver.resolve_coordination.assert_called_once_with(
                    "task/issue-123-test", 123
                )

    def test_qualify_gate_fallback_to_local_blocked_reason(
        self, qualify_gate_service, sample_issue, mock_store
    ):
        """Verify fallback to local blocked_reason when remote unavailable."""
        # Mock CoordinationResolver to return local blocked_reason (degraded mode)
        mock_truth = CoordinationTruth(
            blocked_reason="Local block from SQLite",
            blocked_reason_source=DataSource.LOCAL_SQLITE,
            blocked_by_issue=None,
            blocked_by_issue_source=None,
            dependencies=[],
            dependencies_source=None,
            worktree_path="/tmp/worktree",
            actor="executor",
        )

        with patch.object(
            qualify_gate_service._coordination_resolver,
            "resolve_coordination",
            return_value=mock_truth,
        ):
            mock_label_port = Mock()
            with patch(
                "vibe3.domain.qualify_gate.GhIssueLabelPort",
                return_value=mock_label_port,
            ):
                flow_state = {"status": "active"}

                result = qualify_gate_service.run_qualify_gate(
                    issue=sample_issue,
                    branch="task/issue-123-test",
                    flow_state=flow_state,
                    labels=["state/in-progress"],
                    trigger_state=IssueState.IN_PROGRESS,
                )

                # Verify still blocked by local reason
                assert result is None
                mock_label_port.add_issue_label.assert_called_once_with(
                    123, "state/blocked"
                )


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
            blocked_by_issue=None,
            blocked_by_issue_source=None,
            dependencies=[456, 789],  # Remote dependencies
            dependencies_source=DataSource.ISSUE_BODY_FALLBACK,
            worktree_path="/tmp/worktree",
            actor="executor",
        )

        with patch.object(
            qualify_gate_service._coordination_resolver,
            "resolve_coordination",
            return_value=mock_truth,
        ):
            # Mock dependency satisfaction check (both unresolved)
            qualify_gate_service._is_dependency_satisfied = Mock(return_value=False)

            mock_label_port = Mock()
            with patch(
                "vibe3.domain.qualify_gate.GhIssueLabelPort",
                return_value=mock_label_port,
            ):
                flow_state = {"status": "active"}

                result = qualify_gate_service.run_qualify_gate(
                    issue=sample_issue,
                    branch="task/issue-123-test",
                    flow_state=flow_state,
                    labels=["state/in-progress"],
                    trigger_state=IssueState.IN_PROGRESS,
                )

                # Verify blocked by remote dependencies
                assert result is None
                mock_store.update_flow_state.assert_called()
                mock_label_port.add_issue_label.assert_called_once_with(
                    123, "state/blocked"
                )

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
            blocked_by_issue=None,
            blocked_by_issue_source=None,
            dependencies=[456],  # Local dependencies
            dependencies_source=DataSource.LOCAL_SQLITE,
            worktree_path="/tmp/worktree",
            actor="executor",
        )

        with patch.object(
            qualify_gate_service._coordination_resolver,
            "resolve_coordination",
            return_value=mock_truth,
        ):
            # Mock dependency satisfaction check (unresolved)
            qualify_gate_service._is_dependency_satisfied = Mock(return_value=False)

            mock_label_port = Mock()
            with patch(
                "vibe3.domain.qualify_gate.GhIssueLabelPort",
                return_value=mock_label_port,
            ):
                flow_state = {"status": "active"}

                result = qualify_gate_service.run_qualify_gate(
                    issue=sample_issue,
                    branch="task/issue-123-test",
                    flow_state=flow_state,
                    labels=["state/in-progress"],
                    trigger_state=IssueState.IN_PROGRESS,
                )

                # Verify still blocked by local dependencies
                assert result is None
                mock_store.update_flow_state.assert_called()
                mock_label_port.add_issue_label.assert_called_once_with(
                    123, "state/blocked"
                )

    def test_qualify_gate_remote_blocked_by_issue(
        self, qualify_gate_service, sample_issue, mock_store
    ):
        """Verify remote blocked_by_issue is used when available."""
        # Mock CoordinationResolver to return remote blocked_by_issue
        mock_truth = CoordinationTruth(
            blocked_reason=None,
            blocked_reason_source=None,
            blocked_by_issue=456,  # Remote blocked_by_issue
            blocked_by_issue_source=DataSource.ISSUE_BODY_FALLBACK,
            dependencies=[],
            dependencies_source=None,
            worktree_path=None,  # No worktree to avoid health check blocking
            actor="executor",
        )

        with patch.object(
            qualify_gate_service._coordination_resolver,
            "resolve_coordination",
            return_value=mock_truth,
        ):
            # Mock FlowState model
            from vibe3.models.flow import FlowState

            mock_flow_state_obj = Mock()
            mock_flow_state_obj.status = "active"

            with patch.object(
                FlowState, "model_validate", return_value=mock_flow_state_obj
            ):
                # Mock infer_resume_label
                with patch(
                    "vibe3.domain.qualify_gate.infer_resume_label",
                    return_value=IssueState.IN_PROGRESS,
                ):
                    mock_label_port = Mock()
                    with patch(
                        "vibe3.domain.qualify_gate.GhIssueLabelPort",
                        return_value=mock_label_port,
                    ):
                        # Mock get_flows_by_issue for source_pr lookup
                        mock_store.get_flows_by_issue.return_value = []

                        flow_state = {"status": "active"}

                        result = qualify_gate_service.run_qualify_gate(
                            issue=sample_issue,
                            branch="task/issue-123-test",
                            flow_state=flow_state,
                            labels=["state/blocked"],
                            trigger_state=IssueState.BLOCKED,
                        )

                        # Verify unblock handling uses remote blocked_by_issue
                        # (should update flow state to clear blocked_by_issue)
                        assert result == IssueState.IN_PROGRESS
                        mock_store.update_flow_state.assert_called()
                        mock_label_port.remove_issue_label.assert_called_once_with(
                            123, "state/blocked"
                        )
                        mock_label_port.add_issue_label.assert_called_once_with(
                            123, "state/in-progress"
                        )


class TestProvenanceTracking:
    """Tests for provenance tracking via DataSource."""

    def test_provenance_remote_blocked_reason(self, qualify_gate_service, sample_issue):
        """Verify provenance is tracked for remote blocked_reason."""
        mock_truth = CoordinationTruth(
            blocked_reason="Remote block",
            blocked_reason_source=DataSource.ISSUE_BODY_FALLBACK,
            blocked_by_issue=None,
            blocked_by_issue_source=None,
            dependencies=[],
            dependencies_source=None,
            worktree_path="/tmp/worktree",
            actor="executor",
        )

        with patch.object(
            qualify_gate_service._coordination_resolver,
            "resolve_coordination",
            return_value=mock_truth,
        ):
            with patch(
                "vibe3.domain.qualify_gate.GhIssueLabelPort",
                return_value=Mock(),
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
                assert truth.blocked_reason_source == DataSource.ISSUE_BODY_FALLBACK

    def test_provenance_local_dependencies(self, qualify_gate_service, sample_issue):
        """Verify provenance is tracked for local dependencies."""
        mock_truth = CoordinationTruth(
            blocked_reason=None,
            blocked_reason_source=None,
            blocked_by_issue=None,
            blocked_by_issue_source=None,
            dependencies=[456],
            dependencies_source=DataSource.LOCAL_SQLITE,
            worktree_path="/tmp/worktree",
            actor="executor",
        )

        with patch.object(
            qualify_gate_service._coordination_resolver,
            "resolve_coordination",
            return_value=mock_truth,
        ):
            qualify_gate_service._is_dependency_satisfied = Mock(return_value=False)

            with patch(
                "vibe3.domain.qualify_gate.GhIssueLabelPort",
                return_value=Mock(),
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
                assert truth.dependencies_source == DataSource.LOCAL_SQLITE
