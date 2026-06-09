"""Tests for issue loader bulk operations."""

from unittest.mock import MagicMock

from vibe3.models import OrchestraConfig
from vibe3.orchestra.issue_loader import get_flow_context_bulk


def test_get_flow_context_bulk_assembles_result() -> None:
    """Bulk context retrieval should assemble flow contexts correctly."""
    # Mock dependencies
    mock_store = MagicMock()
    mock_flow_manager = MagicMock()
    mock_config = MagicMock(spec=OrchestraConfig)
    mock_github = MagicMock()

    # Setup mock responses
    mock_store.get_flows_by_issues_bulk.return_value = {
        100: [{"branch": "task/issue-100", "flow_status": "active"}],
        200: [{"branch": "task/issue-200", "flow_status": "active"}],
    }

    mock_flow_manager.resolve_best_flow.side_effect = lambda issue_num, flows: (
        flows[0] if flows else None
    )

    mock_store.get_flow_state_bulk.return_value = {
        "task/issue-100": {"branch": "task/issue-100", "flow_status": "active"},
        "task/issue-200": {"branch": "task/issue-200", "flow_status": "active"},
    }

    # Execute bulk retrieval
    result = get_flow_context_bulk(
        [100, 200], mock_config, mock_github, mock_store, mock_flow_manager
    )

    # Verify result structure
    assert len(result) == 2
    assert result[100] == (
        "task/issue-100",
        {"branch": "task/issue-100", "flow_status": "active"},
    )
    assert result[200] == (
        "task/issue-200",
        {"branch": "task/issue-200", "flow_status": "active"},
    )


def test_get_flow_context_bulk_empty_input() -> None:
    """Bulk retrieval with empty list should return empty dict."""
    mock_store = MagicMock()
    mock_flow_manager = MagicMock()
    mock_config = MagicMock(spec=OrchestraConfig)
    mock_github = MagicMock()

    result = get_flow_context_bulk(
        [], mock_config, mock_github, mock_store, mock_flow_manager
    )

    assert result == {}
    mock_store.get_flows_by_issues_bulk.assert_not_called()


def test_get_flow_context_bulk_issue_with_no_flow() -> None:
    """Bulk retrieval should return empty context for issues without flows."""
    mock_store = MagicMock()
    mock_flow_manager = MagicMock()
    mock_config = MagicMock(spec=OrchestraConfig)
    mock_github = MagicMock()

    # Setup mock responses - issue 100 has flow, issue 999 does not
    mock_store.get_flows_by_issues_bulk.return_value = {
        100: [{"branch": "task/issue-100", "flow_status": "active"}],
        999: [],
    }

    def mock_resolve(issue_num: int, flows: list) -> dict | None:
        if issue_num == 100:
            return flows[0]
        return None

    mock_flow_manager.resolve_best_flow.side_effect = mock_resolve

    mock_store.get_flow_state_bulk.return_value = {
        "task/issue-100": {"branch": "task/issue-100", "flow_status": "active"},
    }

    # Execute bulk retrieval
    result = get_flow_context_bulk(
        [100, 999], mock_config, mock_github, mock_store, mock_flow_manager
    )

    # Verify result
    assert len(result) == 2
    assert result[100] == (
        "task/issue-100",
        {"branch": "task/issue-100", "flow_status": "active"},
    )
    assert result[999] == ("", None)
