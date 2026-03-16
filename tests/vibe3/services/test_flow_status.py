"""Tests for Flow status and listing functionality."""

from vibe3.services.flow_service import FlowService


class TestFlowStatus:
    """Tests for retrieving flow status."""

    def test_get_flow_status_success(self, mock_store) -> None:
        """Test getting flow status."""
        mock_store.get_issue_links.return_value = [
            {
                "branch": "test-branch",
                "issue_number": 101,
                "issue_role": "task",
                "created_at": "2026-03-16T00:00:00",
            }
        ]

        service = FlowService(store=mock_store)
        result = service.get_flow_status("test-branch")

        assert result is not None
        assert result.branch == "test-branch"
        assert result.flow_slug == "test-flow"
        assert len(result.issues) == 1
        assert result.issues[0].issue_number == 101

    def test_get_flow_status_not_found(self, mock_store) -> None:
        """Test getting flow status when not found."""
        mock_store.get_flow_state.return_value = None

        service = FlowService(store=mock_store)
        result = service.get_flow_status("nonexistent-branch")

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
                "flow_status": "idle",
                "updated_at": "2026-03-16T00:00:00",
            },
        ]

        service = FlowService(store=mock_store)
        result = service.list_flows()

        assert len(result) == 2
        assert result[0].flow_slug == "flow-1"
        assert result[1].flow_slug == "flow-2"

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
                "flow_status": "idle",
                "updated_at": "2026-03-16T00:00:00",
            },
        ]

        service = FlowService(store=mock_store)
        result = service.list_flows(status="active")

        assert len(result) == 1
        assert result[0].flow_slug == "flow-1"
        assert result[0].flow_status == "active"
