"""Tests for flow status and listing."""

from unittest.mock import MagicMock, patch

import pytest

from vibe3.services.flow_service import FlowService


@pytest.fixture
def mock_store():
    """Mock SQLite client."""
    return MagicMock()


class TestFlowStatus:
    """Tests for individual flow status."""

    def test_get_flow_status_success(self, mock_store) -> None:
        """Test getting flow status successfully."""
        mock_store.get_flow_state.return_value = {
            "branch": "test-branch",
            "flow_slug": "test-slug",
            "flow_status": "active",
            "updated_at": "2026-03-16T00:00:00",
        }
        mock_store.get_issue_links.return_value = []

        service = FlowService(store=mock_store)
        # GitHubClient is imported inside get_flow_status, need to patch it
        with patch("vibe3.services.flow_query_mixin.GitHubClient") as mock_gh_class:
            mock_gh = mock_gh_class.return_value
            mock_gh.get_pr.return_value = None

            result = service.get_flow_status("test-branch")

        assert result is not None
        assert result.branch == "test-branch"
        assert result.flow_status == "active"

    def test_get_flow_status_not_found(self, mock_store) -> None:
        """Test getting flow status for non-existent branch."""
        mock_store.get_flow_state.return_value = None

        service = FlowService(store=mock_store)
        result = service.get_flow_status("non-existent")

        assert result is None


class TestFlowList:
    """Tests for listing flows."""

    def test_list_flows_no_filter(self, mock_store) -> None:
        """Test listing all flows."""
        mock_store.get_all_flows.return_value = [
            {
                "branch": "branch-1",
                "flow_slug": "flow-1",
                "flow_status": "active",
                "updated_at": "2026-03-16T00:00:00",
            },
            {
                "branch": "branch-2",
                "flow_slug": "flow-2",
                "flow_status": "blocked",
                "updated_at": "2026-03-16T00:00:00",
            },
        ]
        mock_store.get_issue_links.return_value = []

        service = FlowService(store=mock_store)
        result = service.list_flows()

        assert len(result) == 2
        assert result[0].branch == "branch-1"
        assert result[1].branch == "branch-2"

    def test_list_flows_with_status_filter(self, mock_store) -> None:
        """Test listing flows with status filter."""
        mock_store.get_all_flows.return_value = [
            {
                "branch": "branch-1",
                "flow_slug": "flow-1",
                "flow_status": "active",
                "updated_at": "2026-03-16T00:00:00",
            },
            {
                "branch": "branch-2",
                "flow_slug": "flow-2",
                "flow_status": "blocked",
                "updated_at": "2026-03-16T00:00:00",
            },
        ]
        mock_store.get_issue_links.return_value = []

        service = FlowService(store=mock_store)
        result = service.list_flows(status="active")

        assert len(result) == 1
        assert result[0].branch == "branch-1"

    def test_list_flows_skips_unparseable_rows(self, mock_store) -> None:
        """Test list_flows skips rows with unknown flow_status without crashing."""
        mock_store.get_all_flows.return_value = [
            {
                "branch": "branch-ok",
                "flow_slug": "flow-ok",
                "flow_status": "active",
                "updated_at": "2026-03-16T00:00:00",
            },
            {
                "branch": "branch-bad",
                "flow_slug": "flow-bad",
                "flow_status": "unknown_future_status",
                "updated_at": "2026-03-16T00:00:00",
            },
        ]
        mock_store.get_issue_links.return_value = []

        service = FlowService(store=mock_store)
        result = service.list_flows()

        assert len(result) == 1
        assert result[0].branch == "branch-ok"
