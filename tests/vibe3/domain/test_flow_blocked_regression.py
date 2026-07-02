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

    def view_issue(self, issue_number: int, **kwargs: object) -> dict:
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

    service.set_block(
        issue_number=123,
        branch="test-branch",
        reason="Test blocking",
        actor="test_actor",
    )

    flow_state = store.get_flow_state("test-branch")
    assert flow_state is not None
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
        "set_block",
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

    service.set_block(
        issue_number=123,
        branch="test-branch",
        reason="Timeline test",
        actor="test_actor",
    )

    # Verify blocked state exists in DB cache
    flow_state = store.get_flow_state("test-branch")
    assert flow_state is not None
    assert flow_state.get("blocked_reason") == "Timeline test"

    # Verify blocked state exists in issue body (authoritative truth)
    body_state = BlockedStateIO(github_client=github).read_body_projection(123)
    assert body_state.is_blocked is True

    # Use raw SQL to directly delete any flow events - verify state remains intact.
    # This proves the DB cache (not timeline events) is the authoritative local source.
    events = store.get_events("test-branch")
    if events:
        import sqlite3

        event_id = events[0]["id"]
        with sqlite3.connect(store.db_path) as conn:
            conn.execute("DELETE FROM flow_events WHERE id = ?", (event_id,))

    # Verify blocked state is still present in DB cache
    flow_state_after = store.get_flow_state("test-branch")
    assert flow_state_after is not None
    assert flow_state_after.get("blocked_reason") == "Timeline test"


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


# ============================================================================
# Truth Table Validation Tests (Required by Issue #3289)
# ============================================================================


class TestAutoResumeTruthTable:
    """Tests for mandatory truth table from issue #3289.

    Truth table validation:
    | human reason | dependency truth | caller | Result |
    |---|---|---|---|
    | present | none/closed | auto | remain blocked; zero mutation |
    | present | open | auto | remain blocked; zero mutation |
    | absent | any open | auto | remain blocked; zero mutation |
    | absent | unreadable | auto | remain blocked; degraded/fail closed |
    | absent | all closed | auto, existing flow | handoff + audited dependency resolution |
    | present | all closed | manual | clear reason, then handoff/explicit target |
    | any | any open | manual without force | remain blocked and report open deps |
    """

    def test_auto_path_human_reason_present_no_mutation(self) -> None:
        """Auto path with human reason present → remain blocked; zero mutation."""
        from unittest.mock import MagicMock

        from vibe3.services.flow.resume_api import evaluate_auto_resume

        with patch("vibe3.services.flow.resume_api.BlockedStateIO") as mock_io_class:
            mock_io = MagicMock()
            mock_io_class.return_value = mock_io

            mock_io.github.get_issue_body.return_value = """<!-- vibe3-flow-state-start -->

**Vibe3 Flow State**

- **State**: blocked
- **Blocked reason**: Manual review required

<!-- vibe3-flow-state-end -->
"""
            mock_io.read_issue_state.return_value = IssueState.BLOCKED

            decision = evaluate_auto_resume(
                issue_number=123,
                branch="task/issue-123",
                github_client=MagicMock(),
            )

            assert not decision.eligible
            # Verify no mutations were made
            assert not mock_io.write_projection.called
            assert not mock_io.write_label_state.called

    def test_auto_path_open_dependency_no_mutation(self) -> None:
        """Auto path with open dependency → remain blocked; zero mutation."""
        from unittest.mock import MagicMock

        from vibe3.services.flow.resume_api import evaluate_auto_resume

        with patch("vibe3.services.flow.resume_api.BlockedStateIO") as mock_io_class:
            mock_io = MagicMock()
            mock_io_class.return_value = mock_io

            mock_io.github.get_issue_body.return_value = """<!-- vibe3-flow-state-start -->

**Vibe3 Flow State**

- **State**: blocked
- **Blocked by**: #456

<!-- vibe3-flow-state-end -->
"""
            mock_io.read_issue_state.return_value = IssueState.BLOCKED

            with patch(
                "vibe3.services.flow.resume_api.DependencyResolutionService.is_dependency_resolved"
            ) as mock_resolved:
                mock_resolved.return_value = MagicMock(resolved=False)

                decision = evaluate_auto_resume(
                    issue_number=123,
                    branch="task/issue-123",
                    github_client=MagicMock(),
                )

                assert not decision.eligible
                # Verify no mutations were made
                assert not mock_io.write_projection.called
                assert not mock_io.write_label_state.called

    def test_auto_path_all_closed_existing_flow_routes_to_handoff(self) -> None:
        """Auto path with all deps closed + existing flow → handoff."""
        from unittest.mock import MagicMock

        from vibe3.services.flow.resume_api import (
            apply_auto_resume,
            evaluate_auto_resume,
        )

        with patch("vibe3.services.flow.resume_api.BlockedStateIO") as mock_io_class:
            mock_io = MagicMock()
            mock_io_class.return_value = mock_io

            body = """<!-- vibe3-flow-state-start -->

**Vibe3 Flow State**

- **State**: blocked
- **Blocked by**: #456

<!-- vibe3-flow-state-end -->
"""
            mock_io.github.get_issue_body.return_value = body
            mock_io.read_issue_state.return_value = IssueState.BLOCKED
            mock_io.write_label_state.return_value = "advanced"

            with patch(
                "vibe3.services.flow.resume_api.DependencyResolutionService.is_dependency_resolved"
            ) as mock_resolved:
                mock_resolved.return_value = MagicMock(resolved=True)

                # Evaluate
                decision = evaluate_auto_resume(
                    issue_number=123,
                    branch="task/issue-123",
                    github_client=MagicMock(),
                )

                assert decision.eligible

                # Mock existing flow with db_path and count_specific_pair
                mock_store = MagicMock()
                mock_store.get_flow_state.return_value = {"branch": "task/issue-123"}
                mock_store.db_path = ":memory:"
                mock_store.count_specific_pair.return_value = 0
                mock_store.record_confirmed_transition.return_value = (1, 1, 1)

                # Apply
                result = apply_auto_resume(
                    decision,
                    github_client=MagicMock(),
                    store=mock_store,
                )

                assert result.success
                assert result.target_state == IssueState.HANDOFF

    def test_manual_path_clears_reason_after_explicit_authorization(self) -> None:
        """Manual path with all closed deps clears reason after explicit authorization."""
        from unittest.mock import MagicMock

        from vibe3.services.flow.resume_api import manual_resume

        with patch("vibe3.services.flow.resume_api.BlockedStateIO") as mock_io_class:
            mock_io = MagicMock()
            mock_io_class.return_value = mock_io

            mock_io.github.get_issue_body.return_value = """<!-- vibe3-flow-state-start -->

**Vibe3 Flow State**

- **State**: blocked
- **Blocked reason**: Manual review needed

<!-- vibe3-flow-state-end -->
"""
            mock_io.read_issue_state.return_value = IssueState.BLOCKED
            mock_io.write_label_state.return_value = "advanced"

            # Mock store with db_path and count_specific_pair
            mock_store = MagicMock()
            mock_store.db_path = ":memory:"
            mock_store.count_specific_pair.return_value = 0
            mock_store.record_confirmed_transition.return_value = (1, 1, 1)

            result = manual_resume(
                issue_number=123,
                branch="task/issue-123",
                target_state=IssueState.READY,
                actor="cli:user",
                reason="User approved",
                github_client=MagicMock(),
                store=mock_store,
            )

            assert result.success
            # Verify projection was written with cleared reason
            call_args = mock_io.write_projection.call_args
            projection = call_args[0][1]
            assert projection.blocked_reason is None

    def test_manual_path_open_deps_fails_closed(self) -> None:
        """Manual path with open deps → remain blocked and report open deps."""
        from unittest.mock import MagicMock

        from vibe3.services.flow.resume_api import manual_resume

        with patch("vibe3.services.flow.resume_api.BlockedStateIO") as mock_io_class:
            mock_io = MagicMock()
            mock_io_class.return_value = mock_io

            mock_io.github.get_issue_body.return_value = """<!-- vibe3-flow-state-start -->

**Vibe3 Flow State**

- **State**: blocked
- **Blocked by**: #456

<!-- vibe3-flow-state-end -->
"""
            mock_io.read_issue_state.return_value = IssueState.BLOCKED

            with patch(
                "vibe3.services.flow.resume_api.DependencyResolutionService.is_dependency_resolved"
            ) as mock_resolved:
                mock_resolved.return_value = MagicMock(resolved=False)

                # Mock store with db_path and count_specific_pair
                mock_store = MagicMock()
                mock_store.db_path = ":memory:"
                mock_store.count_specific_pair.return_value = 0

                result = manual_resume(
                    issue_number=123,
                    branch="task/issue-123",
                    target_state=IssueState.READY,
                    actor="cli:user",
                    reason="User wants to resume",
                    github_client=MagicMock(),
                    store=mock_store,
                )

                assert not result.success
                assert "456" in result.detail
                # Verify no projection was written
                assert not mock_io.write_projection.called

    def test_no_inference_from_pr_ref_plan_ref(self) -> None:
        """No resume target is inferred solely from pr_ref, plan_ref, or report/audit refs."""
        # This test verifies that evaluate_auto_resume does NOT look at
        # pr_ref/plan_ref/report_ref/audit_ref to determine target state
        # It only routes to handoff for existing flow, or ready for pre-flow
        from unittest.mock import MagicMock

        from vibe3.services.flow.resume_api import (
            apply_auto_resume,
            evaluate_auto_resume,
        )

        with patch("vibe3.services.flow.resume_api.BlockedStateIO") as mock_io_class:
            mock_io = MagicMock()
            mock_io_class.return_value = mock_io

            # Body contains pr_ref and plan_ref
            body = """<!-- vibe3-flow-state-start -->

**Vibe3 Flow State**

- **State**: blocked
- **Blocked by**: #456

<!-- vibe3-flow-state-end -->

## pr_ref
#789

## plan_ref
docs/plans/issue-123-plan.md
"""
            mock_io.github.get_issue_body.return_value = body
            mock_io.read_issue_state.return_value = IssueState.BLOCKED
            mock_io.write_label_state.return_value = "advanced"

            with patch(
                "vibe3.services.flow.resume_api.DependencyResolutionService.is_dependency_resolved"
            ) as mock_resolved:
                mock_resolved.return_value = MagicMock(resolved=True)

                decision = evaluate_auto_resume(
                    issue_number=123,
                    branch="task/issue-123",
                    github_client=MagicMock(),
                )

                assert decision.eligible

                # Mock NO existing flow (pre-flow scenario) with db_path and count_specific_pair
                mock_store = MagicMock()
                mock_store.get_flow_state.return_value = None
                mock_store.db_path = ":memory:"
                mock_store.count_specific_pair.return_value = 0
                mock_store.record_confirmed_transition.return_value = (1, 1, 1)

                result = apply_auto_resume(
                    decision,
                    github_client=MagicMock(),
                    store=mock_store,
                )

                # Should route to READY (pre-flow), not infer from pr_ref/plan_ref
                assert result.success
                assert result.target_state == IssueState.READY
                # Should NOT be DONE or REVIEW based on pr_ref
                assert result.target_state not in [IssueState.DONE, IssueState.REVIEW]
