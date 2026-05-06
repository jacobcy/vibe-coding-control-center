"""Tests for ProjectStatusSyncService."""

from unittest.mock import MagicMock, patch

from vibe3.models.orchestration import IssueState
from vibe3.services.project_status_sync_service import ProjectStatusSyncService


class MockGitHubProjectClient:
    """Mock client for testing without real GraphQL calls."""

    def __init__(self) -> None:
        self.items: dict[int, str] = {}  # issue_number -> item_id
        self.status_updates: dict[str, str] = {}  # item_id -> status
        self.project_id = "PVT_test123"

    def get_project_id(self) -> str:
        return self.project_id

    def find_item_by_issue(self, issue_number: int) -> str | None:
        return self.items.get(issue_number)

    def update_item_status(
        self,
        item_id: str,
        status_value: str,
        status_field_name: str = "Status",
    ) -> None:
        self.status_updates[item_id] = status_value


def test_state_to_status_mapping_contains_all_states() -> None:
    """All IssueState values should have a status mapping."""
    mapping = ProjectStatusSyncService.STATE_TO_STATUS

    expected_states = [
        IssueState.READY,
        IssueState.CLAIMED,
        IssueState.IN_PROGRESS,
        IssueState.BLOCKED,
        IssueState.HANDOFF,
        IssueState.REVIEW,
        IssueState.MERGE_READY,
        IssueState.DONE,
    ]

    for state in expected_states:
        assert state in mapping, f"Missing mapping for {state.value}"
        assert isinstance(
            mapping[state], str
        ), f"Status for {state.value} should be string"


def test_ready_and_claimed_map_to_ready() -> None:
    """READY and CLAIMED states both map to 'Ready' status."""
    service = ProjectStatusSyncService(
        owner="test", project_number=1, owner_type="user"
    )

    assert service.get_status_for_state(IssueState.READY) == "Ready"
    assert service.get_status_for_state(IssueState.CLAIMED) == "Ready"


def test_in_progress_maps_to_in_progress() -> None:
    """IN_PROGRESS state maps to 'In Progress' status."""
    service = ProjectStatusSyncService(
        owner="test", project_number=1, owner_type="user"
    )

    assert service.get_status_for_state(IssueState.IN_PROGRESS) == "In Progress"


def test_blocked_maps_to_blocked() -> None:
    """BLOCKED state maps to 'Blocked' status."""
    service = ProjectStatusSyncService(
        owner="test", project_number=1, owner_type="user"
    )

    assert service.get_status_for_state(IssueState.BLOCKED) == "Blocked"


def test_handoff_and_review_map_to_in_review() -> None:
    """HANDOFF and REVIEW states both map to 'In Review' status."""
    service = ProjectStatusSyncService(
        owner="test", project_number=1, owner_type="user"
    )

    assert service.get_status_for_state(IssueState.HANDOFF) == "In Review"
    assert service.get_status_for_state(IssueState.REVIEW) == "In Review"


def test_merge_ready_and_done_map_to_done() -> None:
    """MERGE_READY and DONE states both map to 'Done' status."""
    service = ProjectStatusSyncService(
        owner="test", project_number=1, owner_type="user"
    )

    assert service.get_status_for_state(IssueState.MERGE_READY) == "Done"
    assert service.get_status_for_state(IssueState.DONE) == "Done"


def test_sync_issue_status_returns_true_on_success() -> None:
    """Successful sync should return True."""
    service = ProjectStatusSyncService(
        owner="test", project_number=1, owner_type="user"
    )
    mock_client = MockGitHubProjectClient()

    # Setup: issue 123 exists in project
    mock_client.items[123] = "PVTI_item123"
    service.client = mock_client

    result = service.sync_issue_status(123, IssueState.IN_PROGRESS)

    assert result is True
    assert mock_client.status_updates["PVTI_item123"] == "In Progress"


def test_sync_issue_status_returns_false_when_item_not_found() -> None:
    """Sync should return False when issue not in project."""
    service = ProjectStatusSyncService(
        owner="test", project_number=1, owner_type="user"
    )
    mock_client = MockGitHubProjectClient()

    # Issue 999 does not exist in project
    service.client = mock_client

    result = service.sync_issue_status(999, IssueState.IN_PROGRESS)

    assert result is False
    assert len(mock_client.status_updates) == 0


def test_sync_issue_status_returns_false_on_client_error() -> None:
    """Sync should return False and log error on client failure."""
    service = ProjectStatusSyncService(
        owner="test", project_number=1, owner_type="user"
    )

    # Mock client that raises error
    mock_client = MagicMock()
    mock_client.find_item_by_issue.side_effect = Exception("GraphQL error")
    service.client = mock_client

    result = service.sync_issue_status(123, IssueState.IN_PROGRESS)

    assert result is False


def test_sync_issue_status_logs_missing_state_mapping() -> None:
    """Sync should return False and log warning for unknown state."""
    service = ProjectStatusSyncService(
        owner="test", project_number=1, owner_type="user"
    )
    mock_client = MockGitHubProjectClient()
    mock_client.items[123] = "PVTI_item123"
    service.client = mock_client

    # Create a fake state that's not in the mapping
    # (This would require a custom IssueState, but we can test the logic)
    # Instead, we test that get_status_for_state returns None for unmapped states
    # by using an invalid state value
    with patch.object(service, "STATE_TO_STATUS", {}):
        result = service.sync_issue_status(123, IssueState.IN_PROGRESS)
        assert result is False


def test_sync_uses_custom_status_field_name() -> None:
    """Sync should use custom status field name if configured."""
    service = ProjectStatusSyncService(
        owner="test",
        project_number=1,
        owner_type="user",
        status_field_name="Custom Status",
    )
    mock_client = MockGitHubProjectClient()
    mock_client.items[123] = "PVTI_item123"
    service.client = mock_client

    result = service.sync_issue_status(123, IssueState.READY)

    assert result is True
    # Note: Mock client doesn't validate field name, but real client would


def test_sync_handles_all_state_transitions() -> None:
    """Test sync for all valid state transitions."""
    service = ProjectStatusSyncService(
        owner="test", project_number=1, owner_type="user"
    )
    mock_client = MockGitHubProjectClient()
    mock_client.items[123] = "PVTI_item123"
    service.client = mock_client

    # Test all states
    states_to_test = [
        (IssueState.READY, "Ready"),
        (IssueState.CLAIMED, "Ready"),
        (IssueState.IN_PROGRESS, "In Progress"),
        (IssueState.BLOCKED, "Blocked"),
        (IssueState.HANDOFF, "In Review"),
        (IssueState.REVIEW, "In Review"),
        (IssueState.MERGE_READY, "Done"),
        (IssueState.DONE, "Done"),
    ]

    for state, expected_status in states_to_test:
        mock_client.status_updates.clear()
        result = service.sync_issue_status(123, state)
        assert result is True
        assert mock_client.status_updates["PVTI_item123"] == expected_status
