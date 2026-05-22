"""Shared fixtures and helpers for execution module tests."""

from unittest.mock import MagicMock


def _make_mock_conn() -> MagicMock:
    """Create a mock sqlite connection for transition_history operations."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = (1,)  # event_id
    mock_cursor.execute.return_value = mock_cursor  # Return same cursor for chaining
    mock_conn.cursor.return_value = mock_cursor
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    return mock_conn


def _make_mock_store() -> MagicMock:
    """Create a mock SQLiteClient."""
    store = MagicMock()
    store.get_flow_state.return_value = {}
    store.count_specific_pair.return_value = 0  # No previous transitions
    store.record_transition.return_value = None  # Mock record_transition
    store.db_path = ":memory:"  # Use in-memory database for tests
    return store


def _make_github_issue_payload(state_label: str = "state/plan") -> dict:
    """Build a GitHub issue payload dict with given state label."""
    labels = [{"name": state_label}] if state_label else []
    return {"labels": labels, "state": "open"}
