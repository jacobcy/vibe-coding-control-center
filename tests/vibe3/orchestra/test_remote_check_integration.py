"""Tests for remote label check integration in dispatch coordinator."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.orchestra.global_dispatch_coordinator import (
    GlobalDispatchCoordinator,
)
from vibe3.orchestra.queue_operations import select_ready_issues_from_collected_issues
from vibe3.orchestra.queue_persistence_service import QueuePersistenceService
from vibe3.services import should_skip_from_queue


@pytest.fixture
def make_coordinator_with_remote_check() -> callable:
    """Factory for creating GlobalDispatchCoordinator with remote check support."""

    def _make_coordinator(
        remote_check_runner: callable | None = None,
        remote_check_interval: int = 20,
        last_remote_check_tick: int = 0,
    ) -> GlobalDispatchCoordinator:
        config = OrchestraConfig(repo="owner/repo")
        config.manager_usernames = ["manager-bot"]
        config.supervisor_handoff.issue_label = "supervisor"

        capacity = MagicMock()
        capacity.config.max_concurrent_flows = 10
        capacity.get_capacity_status = MagicMock(
            return_value={
                "remaining": 10,
                "active_count": 0,
                "max_capacity": 10,
            }
        )
        capacity._backend = None

        github = MagicMock()
        store = MagicMock()
        store.db_path = ":memory:"
        store.get_flow_state = MagicMock(return_value=None)
        store.get_flows_by_issue = MagicMock(return_value=[])

        flow_manager = MagicMock()
        flow_manager.get_flow_for_issue = MagicMock(return_value=None)

        flow_blocker = MagicMock()

        def mock_issue_loader(issue_number: int):
            return None

        def mock_flow_context_resolver(issue_number: int):
            return (f"task/issue-{issue_number}", None)

        queue_persistence = QueuePersistenceService(
            store=store,
            config=config,
            github=github,
            registry=None,
            supervisor_label=config.supervisor_handoff.issue_label,
            load_issue=mock_issue_loader,
            queue_filter=should_skip_from_queue,
        )

        coordinator = GlobalDispatchCoordinator(
            config=config,
            capacity=capacity,
            github=github,
            store=store,
            flow_manager=flow_manager,
            registry=None,
            flow_blocker=flow_blocker,
            queue_persistence=queue_persistence,
            issue_loader=mock_issue_loader,
            flow_context_resolver=mock_flow_context_resolver,
            queue_selector=select_ready_issues_from_collected_issues,
            check_service=MagicMock(),
            queue_filter=should_skip_from_queue,
            remote_check_runner=remote_check_runner,
            remote_check_interval=remote_check_interval,
        )

        # Set last remote check tick for testing interval logic
        coordinator._last_remote_check_tick = last_remote_check_tick

        return coordinator

    return _make_coordinator


class TestRemoteCheckIntegration:
    """Tests for periodic remote label check in dispatch coordinator."""

    @pytest.mark.asyncio
    async def test_coordinate_does_not_run_remote_check_on_first_tick(
        self, make_coordinator_with_remote_check
    ) -> None:
        """Remote check should NOT run on tick 0 (interval not elapsed)."""
        remote_check_runner = MagicMock()
        coordinator = make_coordinator_with_remote_check(
            remote_check_runner=remote_check_runner,
            remote_check_interval=20,
            last_remote_check_tick=0,
        )

        await coordinator.coordinate(tick_id=0)

        remote_check_runner.assert_not_called()

    @pytest.mark.asyncio
    async def test_coordinate_skips_remote_check_within_interval(
        self, make_coordinator_with_remote_check
    ) -> None:
        """Remote check should NOT run within interval."""
        remote_check_runner = MagicMock()
        coordinator = make_coordinator_with_remote_check(
            remote_check_runner=remote_check_runner,
            remote_check_interval=20,
            last_remote_check_tick=15,
        )

        await coordinator.coordinate(tick_id=20)

        remote_check_runner.assert_not_called()

    @pytest.mark.asyncio
    async def test_coordinate_runs_remote_check_after_interval(
        self, make_coordinator_with_remote_check
    ) -> None:
        """Remote check should run when interval has passed."""
        remote_check_runner = MagicMock()
        coordinator = make_coordinator_with_remote_check(
            remote_check_runner=remote_check_runner,
            remote_check_interval=20,
            last_remote_check_tick=0,
        )

        await coordinator.coordinate(tick_id=20)

        remote_check_runner.assert_called_once()

    @pytest.mark.asyncio
    async def test_coordinate_updates_last_remote_check_tick(
        self, make_coordinator_with_remote_check
    ) -> None:
        """Remote check should update last check tick after successful run."""
        remote_check_runner = MagicMock()
        coordinator = make_coordinator_with_remote_check(
            remote_check_runner=remote_check_runner,
            remote_check_interval=20,
            last_remote_check_tick=0,
        )

        await coordinator.coordinate(tick_id=20)

        assert coordinator._last_remote_check_tick == 20

    @pytest.mark.asyncio
    async def test_coordinate_handles_remote_check_failure(
        self, make_coordinator_with_remote_check
    ) -> None:
        """Remote check failure should be caught and logged, not crash."""
        remote_check_runner = MagicMock(side_effect=Exception("Check failed"))
        coordinator = make_coordinator_with_remote_check(
            remote_check_runner=remote_check_runner,
            remote_check_interval=20,
            last_remote_check_tick=0,
        )

        # Should not raise exception
        await coordinator.coordinate(tick_id=20)

        # Tick should still be updated even on failure
        assert coordinator._last_remote_check_tick == 20

    @pytest.mark.asyncio
    async def test_coordinate_without_remote_check_runner(
        self, make_coordinator_with_remote_check
    ) -> None:
        """Coordinator should work without remote check runner.

        Backward compatibility test.
        """
        coordinator = make_coordinator_with_remote_check(
            remote_check_runner=None,
            remote_check_interval=20,
            last_remote_check_tick=0,
        )

        # Should not raise exception
        await coordinator.coordinate(tick_id=20)

        # No remote check should be recorded
        assert coordinator._last_remote_check_tick == 0

    @pytest.mark.asyncio
    async def test_coordinate_respects_custom_interval(
        self, make_coordinator_with_remote_check
    ) -> None:
        """Remote check should respect custom interval."""
        remote_check_runner = MagicMock()
        coordinator = make_coordinator_with_remote_check(
            remote_check_runner=remote_check_runner,
            remote_check_interval=10,
            last_remote_check_tick=5,
        )

        # Tick 10 - interval is 5 ticks (10 - 5 = 5), but interval is 10,
        # so should NOT run
        await coordinator.coordinate(tick_id=10)

        remote_check_runner.assert_not_called()

        # Tick 15 - now interval elapsed (15 - 5 = 10), should run
        await coordinator.coordinate(tick_id=15)

        remote_check_runner.assert_called_once()

    @pytest.mark.asyncio
    async def test_coordinate_multiple_intervals(
        self, make_coordinator_with_remote_check
    ) -> None:
        """Remote check should run multiple times across intervals."""
        remote_check_runner = MagicMock()
        coordinator = make_coordinator_with_remote_check(
            remote_check_runner=remote_check_runner,
            remote_check_interval=20,
            last_remote_check_tick=0,
        )

        # Tick 0: interval not elapsed yet, no check
        await coordinator.coordinate(tick_id=0)
        assert remote_check_runner.call_count == 0

        # Tick 10: within interval, no check
        await coordinator.coordinate(tick_id=10)
        assert remote_check_runner.call_count == 0

        # Tick 20: interval elapsed, runs check
        await coordinator.coordinate(tick_id=20)
        assert remote_check_runner.call_count == 1
        assert coordinator._last_remote_check_tick == 20

        # Tick 40: next interval, runs check
        await coordinator.coordinate(tick_id=40)
        assert remote_check_runner.call_count == 2
        assert coordinator._last_remote_check_tick == 40


class TestRemoteLabelCheck:
    """Tests for remote label anomaly check flow detection."""

    def test_remote_label_check_treats_dev_issue_flow_as_local_flow(
        self, monkeypatch
    ) -> None:
        """dev/issue-N active flows must not be treated as orphan execution."""
        from vibe3.orchestra.remote_check import run_remote_label_check

        config = MagicMock()
        config.repo = "owner/repo"
        config.manager_usernames = ["manager-bot"]

        github = MagicMock()
        github.list_issues.return_value = [
            {
                "number": 123,
                "labels": [{"name": "state/in-progress"}],
                "assignees": [{"login": "manager-bot"}],
            }
        ]

        store = MagicMock()
        store.get_all_flows.return_value = [
            {"branch": "dev/issue-123", "flow_status": "active"}
        ]

        label_port = MagicMock()

        monkeypatch.setattr("vibe3.config.load_orchestra_config", lambda: config)
        monkeypatch.setattr(
            "vibe3.config.get_manager_usernames",
            lambda loaded_config: loaded_config.manager_usernames,
        )
        monkeypatch.setattr("vibe3.clients.GitHubClient", lambda: github)
        monkeypatch.setattr("vibe3.clients.SQLiteClient", lambda: store)
        monkeypatch.setattr("vibe3.clients.GhIssueLabelPort", lambda repo: label_port)

        result = run_remote_label_check(dry_run=False)

        assert result.anomaly_count == 0
        label_port.remove_issue_label.assert_not_called()
        label_port.add_issue_label.assert_not_called()
