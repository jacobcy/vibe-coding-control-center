"""Tests for OrchestrationFacade."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from vibe3.domain.events import (
    GovernanceDecisionRequired,
    GovernanceScanStarted,
    IssueStateChanged,
)
from vibe3.domain.orchestration_facade import OrchestrationFacade
from vibe3.models.orchestration import IssueInfo, IssueState
from vibe3.runtime.event_bus import GitHubEvent


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

    def test_facade_subscribes_to_issue_events(self) -> None:
        facade = OrchestrationFacade()
        assert "issues" in facade.event_types

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
    @patch("vibe3.domain.orchestration_facade.time.monotonic")
    @patch("vibe3.domain.orchestration_facade.OrchestraConfig")
    def test_on_heartbeat_tick_emits_event(
        self,
        mock_config_cls: MagicMock,
        mock_monotonic: MagicMock,
        mock_publish: MagicMock,
    ) -> None:
        """Test that on_heartbeat_tick emits GovernanceScanStarted event."""
        mock_config_cls.from_settings.return_value = MagicMock(
            polling_interval=1,
            governance=MagicMock(interval_ticks=1),
        )
        mock_monotonic.side_effect = [0.0, 1.0, 2.0]
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
    @patch("vibe3.domain.orchestration_facade.time.monotonic")
    @patch("vibe3.domain.orchestration_facade.OrchestraConfig")
    def test_on_heartbeat_tick_respects_absolute_governance_interval(
        self,
        mock_config_cls: MagicMock,
        mock_monotonic: MagicMock,
        mock_publish: MagicMock,
    ) -> None:
        mock_config_cls.from_settings.return_value = MagicMock(
            polling_interval=900,
            governance=MagicMock(interval_ticks=1),
        )
        mock_monotonic.side_effect = [0.0, 60.0, 901.0]

        facade = OrchestrationFacade(tick_count=0)

        facade.on_heartbeat_tick()
        mock_publish.assert_not_called()

        facade.on_heartbeat_tick()
        mock_publish.assert_called_once()
        event = mock_publish.call_args.args[0]
        assert isinstance(event, GovernanceScanStarted)
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

    @patch("vibe3.domain.orchestration_facade.time.monotonic")
    @patch("vibe3.domain.orchestration_facade.OrchestraConfig")
    @patch("vibe3.domain.orchestration_facade.publish")
    def test_facade_does_not_dispatch_directly(
        self,
        mock_publish: MagicMock,
        mock_config_cls: MagicMock,
        mock_monotonic: MagicMock,
        sample_issue_info: IssueInfo,
    ) -> None:
        """Test that facade only publishes events, doesn't dispatch chains."""
        mock_config_cls.from_settings.return_value = MagicMock(
            polling_interval=1,
            governance=MagicMock(interval_ticks=1),
        )
        mock_monotonic.side_effect = [0.0, 1.0]
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

    @pytest.mark.asyncio
    @patch("vibe3.domain.orchestration_facade.publish")
    async def test_handle_event_converts_issue_payload_to_domain_event(
        self,
        mock_publish: MagicMock,
    ) -> None:
        facade = OrchestrationFacade()
        event = GitHubEvent(
            event_type="issues",
            action="labeled",
            payload={
                "issue": {
                    "number": 42,
                    "title": "Test issue",
                    "labels": [{"name": "state/claimed"}],
                    "assignees": [],
                }
            },
            source="webhook",
        )

        await facade.handle_event(event)

        mock_publish.assert_called_once()
        published = mock_publish.call_args.args[0]
        assert isinstance(published, IssueStateChanged)
        assert published.issue_number == 42
        assert published.to_state == "claimed"

    @pytest.mark.asyncio
    @patch("vibe3.domain.orchestration_facade.publish")
    async def test_handle_event_ignores_non_issue_events(
        self,
        mock_publish: MagicMock,
    ) -> None:
        facade = OrchestrationFacade()
        event = GitHubEvent(
            event_type="issue_comment",
            action="created",
            payload={},
            source="webhook",
        )

        await facade.handle_event(event)

        mock_publish.assert_not_called()


class TestOrchestrationFacadeDispatchServices:
    """Tests for dispatch_services integration (P2: unified heartbeat registration)."""

    @pytest.mark.asyncio
    @patch("vibe3.domain.orchestration_facade.publish")
    @patch("vibe3.domain.orchestration_facade.time.monotonic")
    @patch("vibe3.domain.orchestration_facade.OrchestraConfig")
    async def test_on_tick_calls_all_dispatch_services(
        self,
        mock_config_cls: MagicMock,
        mock_monotonic: MagicMock,
        mock_publish: MagicMock,
    ) -> None:
        """on_tick() should call on_tick() on each dispatch service concurrently."""
        mock_config_cls.from_settings.return_value = MagicMock(
            polling_interval=1,
            governance=MagicMock(interval_ticks=1),
            supervisor_handoff=MagicMock(
                issue_label="supervisor",
                handoff_state_label="state/handoff",
            ),
        )
        mock_monotonic.side_effect = [float(i) for i in range(20)]

        mock_service1 = MagicMock()
        mock_service1.on_tick = AsyncMock()
        mock_service2 = MagicMock()
        mock_service2.on_tick = AsyncMock()

        facade = OrchestrationFacade(
            tick_count=0,
            dispatch_services=[mock_service1, mock_service2],
        )

        with patch.object(facade, "on_supervisor_scan", new_callable=AsyncMock):
            await facade.on_tick()

        mock_service1.on_tick.assert_awaited_once()
        mock_service2.on_tick.assert_awaited_once()

    @pytest.mark.asyncio
    @patch("vibe3.domain.orchestration_facade.publish")
    @patch("vibe3.domain.orchestration_facade.time.monotonic")
    @patch("vibe3.domain.orchestration_facade.OrchestraConfig")
    async def test_on_tick_no_dispatch_services_by_default(
        self,
        mock_config_cls: MagicMock,
        mock_monotonic: MagicMock,
        mock_publish: MagicMock,
    ) -> None:
        """on_tick() should work normally when no dispatch_services are provided."""
        mock_config_cls.from_settings.return_value = MagicMock(
            polling_interval=1,
            governance=MagicMock(interval_ticks=1),
            supervisor_handoff=MagicMock(
                issue_label="supervisor",
                handoff_state_label="state/handoff",
            ),
        )
        mock_monotonic.side_effect = [float(i) for i in range(20)]

        facade = OrchestrationFacade(tick_count=0)

        with patch.object(facade, "on_supervisor_scan", new_callable=AsyncMock):
            # Should not raise even with empty dispatch_services
            await facade.on_tick()

    @pytest.mark.asyncio
    @patch("vibe3.domain.orchestration_facade.publish")
    @patch("vibe3.domain.orchestration_facade.append_orchestra_event")
    @patch("vibe3.domain.orchestration_facade.time.monotonic")
    @patch("vibe3.domain.orchestration_facade.OrchestraConfig")
    async def test_on_tick_continues_when_dispatch_service_fails(
        self,
        mock_config_cls: MagicMock,
        mock_monotonic: MagicMock,
        mock_append_event: MagicMock,
        mock_publish: MagicMock,
    ) -> None:
        """on_tick() should not propagate exceptions from dispatch services."""
        mock_config_cls.from_settings.return_value = MagicMock(
            polling_interval=1,
            governance=MagicMock(interval_ticks=1),
            supervisor_handoff=MagicMock(
                issue_label="supervisor",
                handoff_state_label="state/handoff",
            ),
        )
        mock_monotonic.side_effect = [float(i) for i in range(20)]

        failing_service = MagicMock()
        failing_service.service_name = "failing-dispatch"
        failing_service.on_tick = AsyncMock(side_effect=RuntimeError("GitHub down"))
        healthy_service = MagicMock()
        healthy_service.service_name = "healthy-dispatch"
        healthy_service.on_tick = AsyncMock()

        facade = OrchestrationFacade(
            tick_count=0,
            dispatch_services=[failing_service, healthy_service],
        )

        with patch.object(facade, "on_supervisor_scan", new_callable=AsyncMock):
            # Should not raise even if one service fails (return_exceptions=True)
            await facade.on_tick()

        # Healthy service should still have been called
        healthy_service.on_tick.assert_awaited_once()
        mock_append_event.assert_any_call(
            "server",
            "tick error in failing-dispatch: GitHub down",
        )
