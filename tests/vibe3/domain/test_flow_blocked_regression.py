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
from unittest.mock import patch

from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.models import FlowBlocked, IssueState
from vibe3.models.domain_events import DomainEvent
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


class StubIssueFlowService:
    """Stub task issue resolver for FlowService.block_flow tests."""

    def __init__(self, store: SQLiteClient):
        self.store = store

    def resolve_task_issue_number(self, branch: str) -> int:
        return 123


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
    """Assert FlowBlocked is published after BlockedStateService writes state.

    The timeline event is now written by the projection hook, not directly by
    BlockedStateService. This test verifies that state is written before the
    event is published, ensuring proper ordering.
    """
    store = SQLiteClient(db_path=str(tmp_path / "test.db"))
    store.update_flow_state("test-branch", flow_slug="test")

    github = StubGitHubClient()
    label_service = StubLabelService()
    call_order = []

    def publish_after_write(event: DomainEvent) -> None:
        # State should be written before the event is published
        flow_state = store.get_flow_state("test-branch")
        assert flow_state is not None
        assert flow_state.get("flow_status") == "blocked"
        assert flow_state.get("blocked_reason") == "Test reason"
        # Timeline event is NOT written before publish - it's written by projection hook
        events = store.get_events("test-branch")
        assert len(events) == 0, "Timeline event should not exist before projection"
        assert isinstance(event, FlowBlocked)
        call_order.append("event_after_write")

    with (
        patch("vibe3.services.issue.flow.IssueFlowService", StubIssueFlowService),
        patch("vibe3.services.flow.blocked_state_io.GitHubClient", return_value=github),
        patch(
            "vibe3.services.flow.blocked_state_io.LabelService",
            return_value=label_service,
        ),
        patch("vibe3.models.publish") as mock_publish,
    ):
        mock_publish.side_effect = publish_after_write

        flow_service = FlowService(store=store)
        flow_service.block_flow(
            branch="test-branch",
            reason="Test reason",
            actor="test_actor",
        )

    assert call_order == ["event_after_write"]
    assert mock_publish.called


def test_registered_flow_blocked_handlers_do_not_mutate_state(
    tmp_path: Path,
) -> None:
    """Assert registered FlowBlocked handlers never write blocked state."""
    EventPublisher.reset()

    store = SQLiteClient(db_path=str(tmp_path / "test.db"))
    store.update_flow_state("test-branch", flow_slug="test")

    from vibe3.domain import register_event_handlers

    with patch.object(
        BlockedStateService,
        "block",
        side_effect=AssertionError("FlowBlocked handler must not write state"),
    ) as mock_block:
        register_event_handlers()

        test_event = FlowBlocked(
            issue_number=123,
            branch="test-branch",
            blocked_reason="test reason",
            actor="test_actor",
        )
        EventPublisher().publish(test_event)

    assert not mock_block.called

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
    """Assert service-layer repeated blocks preserve body dependencies."""
    store = SQLiteClient(db_path=str(tmp_path / "test.db"))
    store.update_flow_state("test-branch", flow_slug="test")

    github = StubGitHubClient()
    label_service = StubLabelService()

    with (
        patch("vibe3.services.issue.flow.IssueFlowService", StubIssueFlowService),
        patch("vibe3.services.flow.blocked_state_io.GitHubClient", return_value=github),
        patch(
            "vibe3.services.flow.blocked_state_io.LabelService",
            return_value=label_service,
        ),
        patch("vibe3.models.publish"),
    ):
        flow_service = FlowService(store=store)

        flow_service.block_flow(
            branch="test-branch",
            reason=None,
            blocked_by_issue=456,
            actor="test_actor",
        )
        flow_service.block_flow(
            branch="test-branch",
            reason=None,
            blocked_by_issue=789,
            actor="test_actor",
        )

    state = BlockedStateIO(github_client=github).read_body_projection(123)
    assert state.is_blocked is True
    assert state.blocked_by == [456, 789]
