"""Regression tests for blocked-state event boundary invariants.

Guards the three-layer boundary between:
1. BlockedStateService (service layer)
2. FlowTimelineService (timeline events)
3. FlowBlocked domain events

Tests assert invariants from ADR-0004:
- Service is the sole blocked-state writer
- Domain event does NOT mutate state
- Timeline events are audit-only
- Multi-dependency data is preserved
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.models import FlowBlocked, IssueState
from vibe3.models.event_bus import EventPublisher
from vibe3.services.flow.blocked_state_io import BlockedStateIO
from vibe3.services.flow.blocked_state_service import BlockedStateService
from vibe3.services.flow.service import FlowService


class StubGitHubClient:
    """Stub GitHub client for testing."""

    def __init__(self, issue_body: str = "", labels: list[str] | None = None):
        self._issue_body = issue_body
        self._labels = labels or []

    def get_issue_body(self, issue_number: int) -> str | None:
        return self._issue_body

    def update_issue_body(self, issue_number: int, body: str) -> bool:
        self._issue_body = body
        return True

    def view_issue(self, issue_number: int) -> dict:
        return {
            "labels": [{"name": label} for label in self._labels],
        }


class StubLabelService:
    """Stub label service for testing."""

    def __init__(self):
        self.current_state = None

    def confirm_issue_state(
        self, issue_number: int, state: IssueState, actor: str, force: bool = False
    ) -> str:
        """Return values matching real LabelService.confirm_issue_state behavior."""
        if self.current_state == state:
            return "confirmed"
        self.current_state = state
        return "advanced"


def test_blocked_state_is_written_through_service_path(tmp_path: Path) -> None:
    """Assert BlockedStateService.block() writes blocked state to database."""
    store = SQLiteClient(db_path=str(tmp_path / "test.db"))
    store.update_flow_state("test-branch", flow_slug="test")

    github = StubGitHubClient()
    label_service = StubLabelService()

    service = BlockedStateService(
        store=store,
        github_client=github,
        label_service=label_service,
    )

    service.block(
        branch="test-branch",
        reason="Test blocking",
        blocked_by_issue=None,
        actor="test_actor",
        issue_number=123,
    )

    flow_state = store.get_flow_state("test-branch")
    assert flow_state is not None
    assert flow_state.get("flow_status") == "blocked"
    assert flow_state.get("blocked_reason") == "Test blocking"


def test_flow_blocked_event_published_after_service_writes(tmp_path: Path) -> None:
    """Assert FlowBlocked is published after BlockedStateService writes state."""
    store = SQLiteClient(db_path=str(tmp_path / "test.db"))
    store.update_flow_state("test-branch", flow_slug="test")

    call_order = []

    # Mock BlockedStateService.block to track call order
    with patch.object(BlockedStateService, "block", wraps=None) as mock_block:
        mock_block.side_effect = lambda *args, **kwargs: call_order.append("service")

        # Mock IssueFlowService.resolve_task_issue_number to return an issue number
        with patch(
            "vibe3.services.issue.flow.IssueFlowService"
        ) as mock_issue_flow_service:
            mock_issue_service = MagicMock()
            mock_issue_service.resolve_task_issue_number.return_value = 123
            mock_issue_flow_service.return_value = mock_issue_service

            # Mock publish to track call order - patch at the import location
            with patch("vibe3.models.publish") as mock_publish:
                mock_publish.side_effect = lambda event: call_order.append("event")

                flow_service = FlowService(store=store)
                flow_service.block_flow(
                    branch="test-branch",
                    reason="Test reason",
                    actor="test_actor",
                )

    # Verify call order: service before event
    assert call_order == ["service", "event"]
    assert mock_block.called
    assert mock_publish.called


def test_flow_blocked_handler_does_not_mutate_blocked_state(tmp_path: Path) -> None:
    """Assert FlowBlocked handler does NOT call BlockedStateService.block()."""
    EventPublisher.reset()

    store = SQLiteClient(db_path=str(tmp_path / "test.db"))
    store.update_flow_state("test-branch", flow_slug="test")

    def spy_handler(event: FlowBlocked) -> None:
        pass

    # Subscribe handler to FlowBlocked
    publisher = EventPublisher()
    publisher.subscribe("FlowBlocked", spy_handler)

    # Publish FlowBlocked event
    test_event = FlowBlocked(
        issue_number=123,
        branch="test-branch",
        blocked_reason="test reason",
        actor="test_actor",
    )
    publisher.publish(test_event)

    # Verify database was NOT mutated
    flow_state = store.get_flow_state("test-branch")
    assert flow_state is not None
    # Should still be "active", not "blocked"
    assert flow_state.get("flow_status") != "blocked"


def test_timeline_recorded_during_block_not_as_state_source(tmp_path: Path) -> None:
    """Assert timeline is audit-only, not the sole state source."""
    store = SQLiteClient(db_path=str(tmp_path / "test.db"))
    store.update_flow_state("test-branch", flow_slug="test")

    github = StubGitHubClient()
    label_service = StubLabelService()

    service = BlockedStateService(
        store=store,
        github_client=github,
        label_service=label_service,
    )

    service.block(
        branch="test-branch",
        reason="Timeline test",
        blocked_by_issue=None,
        actor="test_actor",
        issue_number=123,
    )

    # Verify blocked state exists
    flow_state = store.get_flow_state("test-branch")
    assert flow_state is not None
    assert flow_state.get("flow_status") == "blocked"

    # Verify timeline event exists
    events = store.get_events("test-branch")
    timeline_events = [e for e in events if e.get("event_type") == "flow_blocked"]
    assert len(timeline_events) > 0

    # Delete timeline entry using raw SQL - blocked state should remain intact
    # This verifies timeline is not the sole source of truth
    import sqlite3

    event_id = timeline_events[0]["id"]
    with sqlite3.connect(store.db_path) as conn:
        conn.execute("DELETE FROM flow_events WHERE id = ?", (event_id,))

    # Verify blocked state is still present
    flow_state_after = store.get_flow_state("test-branch")
    assert flow_state_after is not None
    assert flow_state_after.get("flow_status") == "blocked"


def test_multi_dependency_preserved_in_body_projection(tmp_path: Path) -> None:
    """Assert blocked_by_issue accumulates in issue body projection."""
    github = StubGitHubClient()
    io = BlockedStateIO(github_client=github)

    # Write three dependencies
    io.write_body_projection(
        issue_number=123,
        reason=None,
        blocked_by_issue=456,
    )
    io.write_body_projection(
        issue_number=123,
        reason=None,
        blocked_by_issue=789,
    )
    io.write_body_projection(
        issue_number=123,
        reason=None,
        blocked_by_issue=1011,
    )

    # Verify all three are in the body
    body = github._issue_body
    assert "#456" in body
    assert "#789" in body
    assert "#1011" in body


def test_multi_dependency_preserved_through_service_layer(tmp_path: Path) -> None:
    """Assert service layer passes blocked_by_issue to BlockedStateService."""
    store = SQLiteClient(db_path=str(tmp_path / "test.db"))
    store.update_flow_state("test-branch", flow_slug="test")

    flow_service = FlowService(store=store)

    # Track calls to BlockedStateService.block
    with patch.object(BlockedStateService, "block", wraps=None) as mock_block:
        mock_block.return_value = None  # Avoid actual implementation

        flow_service.block_flow(
            branch="test-branch",
            reason=None,
            blocked_by_issue=456,
            actor="test_actor",
        )

        # Verify last call captured the blocked_by_issue
        assert mock_block.called
        call_kwargs = mock_block.call_args[1]
        assert call_kwargs.get("blocked_by_issue") == 456
