"""Tests for FlowService core operations."""

from unittest.mock import MagicMock, patch

import pytest

from vibe3.services.flow_service import FlowService


@pytest.fixture
def mock_store():
    return MagicMock()


@pytest.fixture
def mock_git():
    return MagicMock()


class TestFlowServiceCreate:
    """Tests for create_flow."""

    def test_create_flow_with_initiated_by(self, mock_store, mock_git):
        service = FlowService(store=mock_store, git_client=mock_git)
        mock_git.get_current_branch.return_value = "feature/test"

        # Mock get_flow_status to return a valid response after creation
        mock_store.get_flow_state.return_value = {
            "branch": "feature/test",
            "flow_slug": "test-flow",
            "flow_status": "active",
            "updated_at": "2026-04-01T00:00:00",
            "initiated_by": "manual",
        }
        mock_store.get_issue_links.return_value = []

        with patch("vibe3.services.flow_query_mixin.GitHubClient") as mock_gh:
            mock_gh.return_value.get_pr.return_value = None

            status = service.create_flow(
                slug="test-flow", branch="feature/test", initiated_by="manual"
            )

        assert status.initiated_by == "manual"
        mock_store.update_flow_state.assert_called_once()
        args, kwargs = mock_store.update_flow_state.call_args
        assert kwargs["initiated_by"] == "manual"
        assert kwargs["flow_slug"] == "test-flow"
