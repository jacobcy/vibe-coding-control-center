"""Tests for OrchestrationFacade."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from vibe3.domain.events import (
    IssueStateChanged,
)
from vibe3.domain.events.governance import GovernanceScanStarted
from vibe3.domain.events.supervisor_apply import SupervisorIssueIdentified
from vibe3.domain.orchestration_facade import OrchestrationFacade
from vibe3.models.orchestration import IssueInfo, IssueState
from vibe3.orchestra.failed_gate import GateResult
from vibe3.runtime.service_protocol import GitHubEvent


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

        assert mock_publish.called

        event = mock_publish.call_args.args[0]
        assert isinstance(event, IssueStateChanged)
        assert event.issue_number == 42
        assert event.from_state == "ready"
        assert event.to_state == "claimed"

    @patch("vibe3.domain.orchestration_facade.publish")
    @patch("vibe3.domain.orchestration_facade.time.monotonic")
    @patch("vibe3.domain.orchestration_facade.OrchestraConfig")
    def test_on_heartbeat_tick_publishes_governance_scan_started(
        self,
        mock_config_cls: MagicMock,
        mock_monotonic: MagicMock,
        mock_publish: MagicMock,
    ) -> None:
        """Test that on_heartbeat_tick publishes GovernanceScanStarted."""
        mock_config_cls.from_settings.return_value = MagicMock(
            polling_interval=1,
            governance=MagicMock(interval_ticks=1),
        )
        mock_monotonic.side_effect = [0.0, 1.0, 2.0]
        facade = OrchestrationFacade(tick_count=0)

        facade.on_heartbeat_tick()

        assert mock_publish.call_count == 1
        event = mock_publish.call_args.args[0]
        assert isinstance(event, GovernanceScanStarted)
        assert event.tick_count == 1

        mock_publish.reset_mock()
        facade.on_heartbeat_tick()
        assert mock_publish.call_count == 1
        event2 = mock_publish.call_args.args[0]
        assert isinstance(event2, GovernanceScanStarted)
        assert event2.tick_count == 2

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
        assert mock_publish.call_count == 1
        event = mock_publish.call_args.args[0]
        assert isinstance(event, GovernanceScanStarted)
        assert event.tick_count == 2

    @patch("vibe3.clients.github_client.GitHubClient.add_comment")
    def test_on_governance_decision_posts_comment(
        self,
        mock_add_comment: MagicMock,
        sample_issue_info: IssueInfo,
    ) -> None:
        """Test that on_governance_decision posts a GitHub comment directly."""
        facade = OrchestrationFacade()
        facade.on_governance_decision(
            issue_info=sample_issue_info,
            reason="Manual review required",
            suggested_action="Assign to reviewer",
        )

        mock_add_comment.assert_called_once()
        call_args = mock_add_comment.call_args
        assert call_args.args[0] == 42
        assert "Manual review required" in call_args.args[1]

    @patch("vibe3.domain.orchestration_facade.publish")
    @patch("vibe3.domain.orchestration_facade.time.monotonic")
    @patch("vibe3.domain.orchestration_facade.OrchestraConfig")
    def test_facade_publishes_only_events_not_dispatch(
        self,
        mock_config_cls: MagicMock,
        mock_monotonic: MagicMock,
        mock_publish: MagicMock,
        sample_issue_info: IssueInfo,
    ) -> None:
        """Test facade only publishes domain events, never does execution assembly."""
        mock_config_cls.from_settings.return_value = MagicMock(
            polling_interval=1,
            governance=MagicMock(interval_ticks=1),
        )
        mock_monotonic.side_effect = [0.0, 1.0]
        facade = OrchestrationFacade()

        facade.on_issue_state_changed(sample_issue_info, from_state="ready")
        facade.on_heartbeat_tick()

        # Both calls produce exactly one publish each.
        assert mock_publish.call_count == 2
        events = [call.args[0] for call in mock_publish.call_args_list]
        event_types = {type(e).__name__ for e in events}
        assert "IssueStateChanged" in event_types
        assert "GovernanceScanStarted" in event_types

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

    @pytest.mark.asyncio
    @patch("vibe3.domain.orchestration_facade.append_orchestra_event")
    async def test_on_tick_blocks_dispatch_when_failed_gate_is_closed(
        self,
        mock_append_event: MagicMock,
    ) -> None:
        """Failed gate should freeze dispatch-intent emission, not heartbeat itself."""
        dispatch_service = MagicMock()
        capacity = MagicMock()
        gate = MagicMock()
        gate.check.return_value = GateResult(
            blocked=True,
            issue_number=328,
            reason="manager failed",
        )

        facade = OrchestrationFacade(
            dispatch_services=[dispatch_service],
            capacity=capacity,
            failed_gate=gate,
        )
        facade.on_supervisor_scan = AsyncMock()
        facade._coordinator = MagicMock()
        facade._coordinator.coordinate = AsyncMock()

        await facade.on_tick()

        gate.check.assert_called_once()
        facade._coordinator.coordinate.assert_not_awaited()
        assert mock_append_event.called
        assert "dispatch blocked by failed gate" in mock_append_event.call_args.args[1]

    @pytest.mark.asyncio
    @patch("vibe3.domain.orchestration_facade.publish")
    @patch("vibe3.clients.github_client.GitHubClient.list_issues")
    @patch("vibe3.domain.orchestration_facade.OrchestraConfig")
    async def test_on_supervisor_scan_publishes_supervisor_issue_identified(
        self,
        mock_config_cls: MagicMock,
        mock_list_issues: MagicMock,
        mock_publish: MagicMock,
    ) -> None:
        """Test that on_supervisor_scan publishes SupervisorIssueIdentified events."""
        mock_config_cls.from_settings.return_value = MagicMock(
            repo="owner/repo",
            supervisor_handoff=MagicMock(
                issue_label="supervisor",
                handoff_state_label="state/handoff",
                supervisor_file="supervisor.md",
            ),
        )
        mock_list_issues.return_value = [
            {
                "number": 99,
                "title": "Governance issue",
                "labels": [
                    {"name": "supervisor"},
                    {"name": "state/handoff"},
                ],
            }
        ]

        facade = OrchestrationFacade()
        await facade.on_supervisor_scan()

        assert mock_publish.call_count == 1
        event = mock_publish.call_args.args[0]
        assert isinstance(event, SupervisorIssueIdentified)
        assert event.issue_number == 99
        assert event.issue_title == "Governance issue"
        assert event.supervisor_file == "supervisor.md"

    @pytest.mark.asyncio
    @patch("vibe3.domain.orchestration_facade.publish")
    @patch("vibe3.clients.github_client.GitHubClient.list_issues")
    @patch("vibe3.domain.orchestration_facade.OrchestraConfig")
    async def test_on_supervisor_scan_skips_missing_labels(
        self,
        mock_config_cls: MagicMock,
        mock_list_issues: MagicMock,
        mock_publish: MagicMock,
    ) -> None:
        """Test that on_supervisor_scan skips issues without both required labels."""
        mock_config_cls.from_settings.return_value = MagicMock(
            repo="owner/repo",
            supervisor_handoff=MagicMock(
                issue_label="supervisor",
                handoff_state_label="state/handoff",
                supervisor_file="supervisor.md",
            ),
        )
        mock_list_issues.return_value = [
            {
                "number": 1,
                "title": "Only supervisor label",
                "labels": [{"name": "supervisor"}],
            },
            {
                "number": 2,
                "title": "Only handoff label",
                "labels": [{"name": "state/handoff"}],
            },
        ]

        facade = OrchestrationFacade()
        await facade.on_supervisor_scan()

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
        """on_tick() should use GlobalDispatchCoordinator to coordinate dispatch."""
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
        mock_service1.role_def = MagicMock()
        mock_service1.role_def.registry_role = "reviewer"
        mock_service1.collect_ready_issues = AsyncMock(return_value=[])
        mock_service2 = MagicMock()
        mock_service2.role_def = MagicMock()
        mock_service2.role_def.registry_role = "executor"
        mock_service2.collect_ready_issues = AsyncMock(return_value=[])

        mock_capacity = MagicMock()
        mock_capacity.can_dispatch.return_value = True
        mock_capacity.get_capacity_status.return_value = {
            "remaining": 1,
            "active_count": 0,
            "max_capacity": 5,
        }

        facade = OrchestrationFacade(
            tick_count=0,
            dispatch_services=[mock_service1, mock_service2],
            capacity=mock_capacity,
        )

        with patch.object(facade, "on_supervisor_scan", new_callable=AsyncMock):
            await facade.on_tick()

        # Verify GlobalDispatchCoordinator is used (via collect_ready_issues)
        mock_service1.collect_ready_issues.assert_awaited_once()
        mock_service2.collect_ready_issues.assert_awaited_once()

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
            await facade.on_tick()

    @pytest.mark.asyncio
    @patch("vibe3.domain.orchestration_facade.publish")
    @patch("vibe3.domain.orchestration_facade.OrchestraConfig")
    async def test_on_tick_continues_when_collect_fails(
        self,
        mock_config_cls: MagicMock,
        mock_publish: MagicMock,
    ) -> None:
        """on_tick() should handle exceptions from collect_ready_issues gracefully.

        GlobalDispatchCoordinator handles errors from collect_ready_issues() internally,
        so facade's on_tick() should complete without raising exceptions.
        """
        mock_config_cls.from_settings.return_value = MagicMock(
            polling_interval=1,
            governance=MagicMock(interval_ticks=1),
            supervisor_handoff=MagicMock(
                issue_label="supervisor",
                handoff_state_label="state/handoff",
            ),
        )

        failing_service = MagicMock()
        failing_service.service_name = "failing-dispatch"
        failing_service.role_def = MagicMock()
        failing_service.role_def.registry_role = "reviewer"
        failing_service.collect_ready_issues = AsyncMock(
            side_effect=RuntimeError("GitHub down")
        )
        healthy_service = MagicMock()
        healthy_service.service_name = "healthy-dispatch"
        healthy_service.role_def = MagicMock()
        healthy_service.role_def.registry_role = "executor"
        healthy_service.collect_ready_issues = AsyncMock(return_value=[])

        mock_capacity = MagicMock()
        mock_capacity.can_dispatch.return_value = False  # Skip all dispatches
        mock_capacity.get_capacity_status.return_value = {
            "remaining": 1,
            "active_count": 4,
            "max_capacity": 5,
        }

        facade = OrchestrationFacade(
            tick_count=0,
            dispatch_services=[failing_service, healthy_service],
            capacity=mock_capacity,
        )

        with (
            patch.object(facade, "on_supervisor_scan", new_callable=AsyncMock),
            patch.object(facade, "on_heartbeat_tick"),
        ):
            # Should not raise, GlobalDispatchCoordinator handles errors internally
            await facade.on_tick()

        # Both services should be called for collection
        failing_service.collect_ready_issues.assert_awaited_once()
        healthy_service.collect_ready_issues.assert_awaited_once()
