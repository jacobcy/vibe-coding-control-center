"""Tests for flow switch branch existence guard."""

from unittest.mock import MagicMock, Mock

import pytest

from vibe3.services.flow_service import FlowService


class TestFlowSwitchBranchGuard:
    """Tests for flow switch branch existence guard."""

    def test_switch_flow_fails_before_stash_when_target_branch_missing(
        self,
        mock_store: Mock,
    ) -> None:
        """Should fail fast and avoid stashing when branch does not exist."""
        mock_store.get_all_flows.return_value = [
            {
                "branch": "task/current-flow",
                "flow_slug": "current_flow",
                "flow_status": "active",
                "updated_at": "2026-03-26T00:00:00",
            }
        ]
        mock_store.get_issue_links.return_value = []

        mock_git = MagicMock()
        mock_git.branch_exists.return_value = False
        mock_git.has_uncommitted_changes.return_value = True

        service = FlowService(store=mock_store, git_client=mock_git)

        with pytest.raises(RuntimeError, match="Branch 'task/current-flow' not found"):
            service.switch_flow("current_flow")

        mock_git.branch_exists.assert_called_once_with("task/current-flow")
        mock_git.stash_push.assert_not_called()
        mock_git.switch_branch.assert_not_called()
        mock_git.stash_apply.assert_not_called()
