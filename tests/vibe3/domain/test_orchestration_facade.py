"""Tests for OrchestrationFacade."""

from unittest.mock import MagicMock, patch

import pytest

from vibe3.domain.events.governance import GovernanceScanStarted
from vibe3.domain.events.supervisor_apply import SupervisorIssueIdentified
from vibe3.domain.orchestration_facade import OrchestrationFacade
from vibe3.models.orchestra_config import GovernanceConfig, OrchestraConfig
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
    @patch("vibe3.domain.orchestration_facade.time.monotonic")
    @patch("vibe3.domain.orchestration_facade.load_orchestra_config")
    def test_on_heartbeat_tick_publishes_governance_scan_started(
        self,
        mock_load_config: MagicMock,
        mock_monotonic: MagicMock,
        mock_publish: MagicMock,
    ) -> None:
        """Test that on_heartbeat_tick publishes GovernanceScanStarted."""
        mock_load_config.return_value = MagicMock(
            polling_interval=1,
            governance=MagicMock(interval_ticks=1),
        )
        # Need 5 values: 2 for first call, 2 for second call, 1 for extra safety
        mock_monotonic.side_effect = [0.0, 1.0, 2.0, 3.0, 4.0]
        facade = OrchestrationFacade(flow_manager=MagicMock(), tick_count=0)

        facade.on_heartbeat_tick()

        assert mock_publish.call_count == 1
        event = mock_publish.call_args.args[0]
        assert isinstance(event, GovernanceScanStarted)
        assert event.tick_count == 1
        assert event.execution_count == 1  # First execution

        mock_publish.reset_mock()
        facade.on_heartbeat_tick()
        assert mock_publish.call_count == 1
        event2 = mock_publish.call_args.args[0]
        assert isinstance(event2, GovernanceScanStarted)
        assert event2.tick_count == 2
        assert event2.execution_count == 2  # Second execution

    @patch("vibe3.domain.orchestration_facade.publish")
    @patch("vibe3.domain.orchestration_facade.time.monotonic")
    @patch("vibe3.domain.orchestration_facade.load_orchestra_config")
    def test_on_heartbeat_tick_respects_absolute_governance_interval(
        self,
        mock_load_config: MagicMock,
        mock_monotonic: MagicMock,
        mock_publish: MagicMock,
    ) -> None:
        mock_load_config.return_value = MagicMock(
            polling_interval=900,
            governance=MagicMock(interval_ticks=1),
        )
        # Need 3 values: 1 for first call (skip), 2 for second call (publish)
        mock_monotonic.side_effect = [0.0, 60.0, 901.0, 901.0]

        facade = OrchestrationFacade(flow_manager=MagicMock(), tick_count=0)

        facade.on_heartbeat_tick()
        mock_publish.assert_not_called()

        facade.on_heartbeat_tick()
        assert mock_publish.call_count == 1
        event = mock_publish.call_args.args[0]
        assert isinstance(event, GovernanceScanStarted)
        assert event.tick_count == 2

    @patch("vibe3.domain.orchestration_facade.publish")
    @patch("vibe3.domain.orchestration_facade.time.monotonic")
    def test_on_heartbeat_tick_uses_injected_runtime_config(
        self,
        mock_monotonic: MagicMock,
        mock_publish: MagicMock,
    ) -> None:
        mock_monotonic.side_effect = [0.0, 60.0, 60.0]
        config = OrchestraConfig(
            polling_interval=60,
            governance=GovernanceConfig(interval_ticks=1),
        )

        facade = OrchestrationFacade(
            flow_manager=MagicMock(), tick_count=0, config=config
        )

        facade.on_heartbeat_tick()

        assert mock_publish.call_count == 1
        event = mock_publish.call_args.args[0]
        assert isinstance(event, GovernanceScanStarted)
        assert event.tick_count == 1

    @patch("vibe3.clients.github_client.GitHubClient.add_comment")
    def test_on_governance_decision_posts_comment(
        self,
        mock_add_comment: MagicMock,
        sample_issue_info: IssueInfo,
    ) -> None:
        """Test that on_governance_decision posts a GitHub comment directly."""
        facade = OrchestrationFacade(flow_manager=MagicMock())
        facade.on_governance_decision(
            issue_info=sample_issue_info,
            reason="Manual review required",
            suggested_action="Assign to reviewer",
        )

        mock_add_comment.assert_called_once()
        call_args = mock_add_comment.call_args
        assert call_args.args[0] == 42
        assert "Manual review required" in call_args.args[1]

    @pytest.mark.asyncio
    @patch(
        "vibe3.roles.supervisor.get_handoff_state_label", return_value="state/handoff"
    )
    @patch("vibe3.domain.orchestration_facade.publish")
    @patch("vibe3.clients.github_client.GitHubClient.list_issues")
    @patch("vibe3.domain.orchestration_facade.load_orchestra_config")
    async def test_on_supervisor_scan_publishes_supervisor_issue_identified(
        self,
        mock_load_config: MagicMock,
        mock_list_issues: MagicMock,
        mock_publish: MagicMock,
        mock_get_handoff_state_label: MagicMock,
    ) -> None:
        """Test that on_supervisor_scan publishes SupervisorIssueIdentified events."""
        mock_load_config.return_value = MagicMock(
            repo="owner/repo",
            supervisor_handoff=MagicMock(
                issue_label="supervisor",
                handoff_state_label="state/handoff",
                interval_ticks=1,
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

        facade = OrchestrationFacade(flow_manager=MagicMock())
        await facade.on_supervisor_scan()

        assert mock_publish.call_count == 1
        event = mock_publish.call_args.args[0]
        assert isinstance(event, SupervisorIssueIdentified)
        assert event.issue_number == 99
        assert event.issue_title == "Governance issue"
        # After migration, supervisor_file comes from recipe, not config
        assert event.supervisor_file == "supervisor/apply.md"

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
        mock_config_cls.return_value = MagicMock(
            repo="owner/repo",
            supervisor_handoff=MagicMock(
                issue_label="supervisor",
                handoff_state_label="state/handoff",
                interval_ticks=1,
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

        facade = OrchestrationFacade(flow_manager=MagicMock())
        await facade.on_supervisor_scan()

        mock_publish.assert_not_called()

    @pytest.mark.asyncio
    @patch(
        "vibe3.roles.supervisor.get_handoff_state_label", return_value="state/handoff"
    )
    @patch("vibe3.domain.orchestration_facade.publish")
    @patch("vibe3.clients.github_client.GitHubClient.list_issues")
    @patch("vibe3.domain.orchestration_facade.load_orchestra_config")
    async def test_on_supervisor_scan_throttles_to_max_dispatch_per_tick(
        self,
        mock_load_config: MagicMock,
        mock_list_issues: MagicMock,
        mock_publish: MagicMock,
        mock_get_handoff_state_label: MagicMock,
    ) -> None:
        """on_supervisor_scan dispatches at most max_dispatch_per_tick events per tick.

        Shares throttle semantics with the manual scan path
        (commands.scan._run_supervisor_scan) via the shared
        select_supervisor_events_for_dispatch helper.
        """
        mock_load_config.return_value = MagicMock(
            repo="owner/repo",
            supervisor_handoff=MagicMock(
                issue_label="supervisor",
                handoff_state_label="state/handoff",
                interval_ticks=1,
                max_dispatch_per_tick=1,
            ),
        )
        mock_list_issues.return_value = [
            {
                "number": 101,
                "title": "Issue A",
                "labels": [{"name": "supervisor"}, {"name": "state/handoff"}],
            },
            {
                "number": 102,
                "title": "Issue B",
                "labels": [{"name": "supervisor"}, {"name": "state/handoff"}],
            },
            {
                "number": 103,
                "title": "Issue C",
                "labels": [{"name": "supervisor"}, {"name": "state/handoff"}],
            },
        ]

        facade = OrchestrationFacade(flow_manager=MagicMock())
        total, dispatched = await facade.on_supervisor_scan()

        assert mock_publish.call_count == 1
        assert total == 3
        assert dispatched == 1
