"""Tests for flow dispatch with waiting-review flows.

Tests the scenario where:
1. Flow F1 exists on worktree W with PR marked ready (pr_ready_marked_at set)
2. New flow F2 for different issue should be allowed to create on W
"""

from unittest.mock import MagicMock, patch

import pytest

from vibe3.execution.flow_dispatch import FlowManager
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.models.orchestration import IssueInfo, IssueState


@pytest.fixture
def mock_store():
    return MagicMock()


@pytest.fixture
def mock_git():
    git = MagicMock()
    git.branch_exists.return_value = True
    git.find_worktree_path_for_branch.return_value = None
    git.create_branch_ref.return_value = None
    return git


@pytest.fixture
def mock_github():
    return MagicMock()


@pytest.fixture
def mock_registry():
    registry = MagicMock()
    registry.count_live_worker_sessions.return_value = 0
    return registry


@pytest.fixture
def flow_manager(mock_store, mock_git, mock_github, mock_registry):
    config = OrchestraConfig(repo="test/repo", max_concurrent_flows=5)
    return FlowManager(
        config,
        store=mock_store,
        git=mock_git,
        github=mock_github,
        registry=mock_registry,
    )


class TestWaitingReviewFlowNotReusable:
    """Test _is_reusable_auto_flow with waiting-review flows."""

    def test_waiting_review_flow_not_reusable(self, flow_manager, mock_store, mock_git):
        """Flow with pr_ready_marked_at should not be reusable."""
        mock_git.branch_exists.return_value = True

        # Flow with PR ready marker
        waiting_flow = {
            "branch": "task/issue-123",
            "flow_status": "active",
            "pr_ready_marked_at": "2026-05-02T10:00:00",
        }

        is_reusable = flow_manager._is_reusable_auto_flow(
            waiting_flow, issue_number=123
        )

        # Should return False (not reusable) - allows new flow creation
        assert is_reusable is False

    def test_active_flow_without_marker_is_reusable(
        self, flow_manager, mock_store, mock_git
    ):
        """Active flow without PR ready marker should be reusable."""
        mock_git.branch_exists.return_value = True

        # Active flow without marker
        active_flow = {
            "branch": "task/issue-456",
            "flow_status": "active",
        }

        is_reusable = flow_manager._is_reusable_auto_flow(active_flow, issue_number=456)

        # Should return True (reusable) - blocks new flow creation
        assert is_reusable is True

    def test_done_flow_not_reusable(self, flow_manager, mock_store, mock_git):
        """Done flow should not be reusable."""
        mock_git.branch_exists.return_value = True

        done_flow = {
            "branch": "task/issue-789",
            "flow_status": "done",
            "pr_ready_marked_at": "2026-05-02T10:00:00",
        }

        is_reusable = flow_manager._is_reusable_auto_flow(done_flow, issue_number=789)

        assert is_reusable is False


class TestCreateFlowAllowsWaitingReview:
    """Test create_flow_for_issue allows new flow when existing is waiting review."""

    def test_new_flow_allowed_when_waiting_review_exists(
        self, flow_manager, mock_store, mock_git, mock_registry
    ):
        """New flow creation for different issue should succeed when existing
        flow is waiting review."""
        # NEW issue #888 (different from existing flow for #999)
        new_issue = IssueInfo(
            number=888,
            title="New task",
            state=IssueState.READY,
            labels=["state/ready"],
        )

        # Existing flow for issue #999 with PR ready marker (waiting review)
        existing_flow = {
            "branch": "task/issue-999",
            "flow_slug": "issue-999",
            "flow_status": "active",
            "pr_ready_marked_at": "2026-05-02T10:00:00",
        }

        # Mock returns NO flows for the new issue #888
        mock_store.get_flows_by_issue.return_value = []

        # Mock returns the waiting-review flow when checking available
        # worktrees. This simulates: worktree has a waiting-review flow,
        # can be reused for new issue.
        mock_store.get_all_flows.return_value = [existing_flow]

        mock_git.branch_exists.return_value = False
        mock_git.find_worktree_path_for_branch.return_value = None

        # Mock capacity check
        mock_registry.count_live_worker_sessions.return_value = 0

        # Mock create_flow - should be called for the NEW issue #888
        with patch.object(flow_manager.flow_service, "create_flow") as mock_create:
            mock_create.return_value = MagicMock(
                branch="task/issue-888",
                flow_slug="issue-888",
                model_dump=lambda: {
                    "branch": "task/issue-888",
                    "flow_slug": "issue-888",
                },
            )

            # Should create new flow for issue #888
            result = flow_manager.create_flow_for_issue(new_issue)

            # Result should be the newly created flow
            assert result is not None
            # create_flow should have been called for the new issue
            mock_create.assert_called_once()
