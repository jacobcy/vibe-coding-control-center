"""Tests for OrchestrationFacade."""

from unittest.mock import MagicMock, patch

import pytest

from vibe3.domain.events import (
    GovernanceDecisionRequired,
    GovernanceScanStarted,
    IssueStateChanged,
)
from vibe3.domain.orchestration_facade import OrchestrationFacade
from vibe3.models.orchestration import IssueInfo, IssueState


@pytest.fixture
def sample_issue_info() -> IssueInfo:
    """Create a sample IssueInfo for testing."""
    return IssueInfo(
        number=42,
        title="Test issue",
        state=IssueState.CLAIMED,
        labels=["state/claimed"],
        assignees=[],
    )


class TestOrchestrationFacade:
    """Tests for OrchestrationFacade."""

    @patch("vibe3.domain.orchestration_facade.publish")
    def test_on_issue_state_changed_emits_event(
        self,
        mock_publish: MagicMock,
        sample_issue_info: IssueInfo,
    ) -> None:
        """Test that on_issue_state_changed emits IssueStateChanged event."""
        facade = OrchestrationFacade()

        facade.on_issue_state_changed(
            issue_info=sample_issue_info,
            from_state="ready",
        )

        # Verify publish was called
        assert mock_publish.called

        # Verify event structure
        event = mock_publish.call_args.args[0]
        assert isinstance(event, IssueStateChanged)
        assert event.issue_number == 42
        assert event.from_state == "ready"
        assert event.to_state == "claimed"

    @patch("vibe3.domain.orchestration_facade.publish")
    def test_on_heartbeat_tick_emits_event(
        self,
        mock_publish: MagicMock,
    ) -> None:
        """Test that on_heartbeat_tick emits GovernanceScanStarted event."""
        facade = OrchestrationFacade(tick_count=0)

        facade.on_heartbeat_tick()

        # Verify publish was called
        assert mock_publish.called

        # Verify event structure
        event = mock_publish.call_args.args[0]
        assert isinstance(event, GovernanceScanStarted)
        assert event.tick_count == 1

        # Second tick should increment counter
        facade.on_heartbeat_tick()
        event = mock_publish.call_args.args[0]
        assert event.tick_count == 2

    @patch("vibe3.domain.orchestration_facade.publish")
    def test_on_governance_decision_emits_event(
        self,
        mock_publish: MagicMock,
        sample_issue_info: IssueInfo,
    ) -> None:
        """Test that on_governance_decision emits GovernanceDecisionRequired event."""
        facade = OrchestrationFacade()

        facade.on_governance_decision(
            issue_info=sample_issue_info,
            reason="Manual review required",
            suggested_action="Assign to reviewer",
        )

        # Verify publish was called
        assert mock_publish.called

        # Verify event structure
        event = mock_publish.call_args.args[0]
        assert isinstance(event, GovernanceDecisionRequired)
        assert event.issue_number == 42
        assert event.reason == "Manual review required"
        assert event.suggested_action == "Assign to reviewer"

    @patch("vibe3.domain.orchestration_facade.publish")
    def test_facade_does_not_dispatch_directly(
        self,
        mock_publish: MagicMock,
        sample_issue_info: IssueInfo,
    ) -> None:
        """Test that facade only publishes events, doesn't dispatch chains."""
        facade = OrchestrationFacade()

        # Call all methods
        facade.on_issue_state_changed(sample_issue_info, from_state="ready")
        facade.on_heartbeat_tick()
        facade.on_governance_decision(sample_issue_info, reason="Test")

        # Verify only publish was called (no direct dispatch)
        assert mock_publish.call_count == 3
        # Verify all events are domain events
        for call in mock_publish.call_args_list:
            event = call.args[0]
            assert isinstance(
                event,
                (IssueStateChanged, GovernanceScanStarted, GovernanceDecisionRequired),
            )
