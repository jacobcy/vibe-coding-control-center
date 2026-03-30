"""Tests for flow task-label sync behavior on flow done."""

from unittest.mock import MagicMock, patch

from vibe3.services.flow_close_ops import sync_flow_done_task_labels


@patch("vibe3.services.flow_close_ops.LabelService")
def test_done_sync_closes_task_when_no_other_open_flows(mock_label_service_cls) -> None:
    store = MagicMock()
    store.get_issue_links.return_value = [{"issue_number": 311, "issue_role": "task"}]
    store.get_flows_by_issue.return_value = [
        {"branch": "task/current", "flow_status": "active"},
        {"branch": "task/other", "flow_status": "done"},
    ]

    sync_flow_done_task_labels(store, "task/current")

    mock_label_service_cls.return_value.confirm_issue_state.assert_called_once()
    call = mock_label_service_cls.return_value.confirm_issue_state.call_args
    assert call.args[0] == 311


@patch("vibe3.services.flow_close_ops.LabelService")
def test_done_sync_skips_task_when_other_open_flow_exists(
    mock_label_service_cls,
) -> None:
    store = MagicMock()
    store.get_issue_links.return_value = [{"issue_number": 311, "issue_role": "task"}]
    store.get_flows_by_issue.return_value = [
        {"branch": "task/current", "flow_status": "active"},
        {"branch": "task/other", "flow_status": "active"},
    ]

    sync_flow_done_task_labels(store, "task/current")

    mock_label_service_cls.return_value.confirm_issue_state.assert_not_called()


@patch("vibe3.services.flow_close_ops.LabelService")
def test_done_sync_ignores_non_task_links(mock_label_service_cls) -> None:
    store = MagicMock()
    store.get_issue_links.return_value = [
        {"issue_number": 311, "issue_role": "related"}
    ]

    sync_flow_done_task_labels(store, "task/current")

    mock_label_service_cls.return_value.confirm_issue_state.assert_not_called()
