"""Tests for GlobalDispatchCoordinator."""

from __future__ import annotations

import re
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.helpers.queue_test_helpers import (
    install_issue_loader,
    make_capacity,
    make_issue,
    make_issue_info,
    make_service,
)
from vibe3.models.orchestration import IssueState
from vibe3.orchestra.global_dispatch_coordinator import (
    MAX_RETRY_COUNT,
    GlobalDispatchCoordinator,
    QueueEntry,
)


class TestGlobalDispatchCoordinator:
    @pytest.fixture(autouse=True)
    def mock_subprocess_run(self):
        """Mock subprocess.run to avoid tmux dependency."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = Exception("tmux not available in tests")
            yield mock_run

    @pytest.mark.asyncio
    async def test_dispatch_all_when_capacity_available(self) -> None:
        issues = [make_issue(1), make_issue(2)]
        service = make_service("planner", issues)
        capacity = make_capacity(remaining=2)
        coordinator = GlobalDispatchCoordinator(capacity, [service])
        install_issue_loader(
            coordinator, {1: IssueState.CLAIMED, 2: IssueState.CLAIMED}
        )
        await coordinator.coordinate()
        assert service._emit_dispatch_intent.call_count == 2

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "role,state,queue_state",
        [
            ("handoff-manager", IssueState.HANDOFF, "claimed"),
            ("manager", IssueState.READY, "ready"),
            ("handoff-manager", IssueState.HANDOFF, "handoff"),
        ],
    )
    async def test_issue_removed_from_frozen_queue(
        self, role: str, state: IssueState, queue_state: str
    ) -> None:
        """Issues that should not be dispatched are removed from queue."""
        issue_num = (
            467
            if role == "handoff-manager"
            else (468 if state == IssueState.READY else 469)
        )
        issue = make_issue(issue_num)
        service = make_service(role, [issue])
        capacity = make_capacity(remaining=1)
        coordinator = GlobalDispatchCoordinator(capacity, [service])
        coordinator._frozen_queue = [
            QueueEntry(
                issue_number=issue_num,
                collected_state=queue_state,
                waiting_state=None,
            )
        ]
        assignees = (
            [] if state != IssueState.HANDOFF or queue_state == "handoff" else []
        )
        coordinator._load_issue = lambda _: make_issue_info(
            issue_num,
            state,
            assignees=assignees,
            labels=(
                ["supervisor", state.to_label()]
                if state == IssueState.HANDOFF
                else None
            ),
        )
        await coordinator.coordinate()
        service._emit_dispatch_intent.assert_not_called()
        assert coordinator._frozen_queue == []

    @pytest.mark.asyncio
    async def test_skip_when_capacity_full(self) -> None:
        issues = [make_issue(1), make_issue(2), make_issue(3)]
        service = make_service("planner", issues)
        capacity = make_capacity(remaining=2)
        coordinator = GlobalDispatchCoordinator(capacity, [service])
        install_issue_loader(
            coordinator,
            {1: IssueState.CLAIMED, 2: IssueState.CLAIMED, 3: IssueState.CLAIMED},
        )
        await coordinator.coordinate()
        assert service._emit_dispatch_intent.call_count == 2

    @pytest.mark.asyncio
    async def test_frozen_queue_prevents_duplicate_dispatch_without_state_change(
        self,
    ) -> None:
        issues = [make_issue(1), make_issue(2)]
        service = make_service("planner", issues)
        capacity = make_capacity(remaining=3)
        coordinator = GlobalDispatchCoordinator(capacity, [service])
        install_issue_loader(
            coordinator, {1: IssueState.CLAIMED, 2: IssueState.CLAIMED}
        )
        await coordinator.coordinate()
        await coordinator.coordinate()
        assert service._emit_dispatch_intent.call_count == 2

    @pytest.mark.asyncio
    async def test_emit_failure_handled_gracefully(self) -> None:
        issue1, issue2 = make_issue(1), make_issue(2)
        service = make_service("planner", [issue1, issue2])
        service._emit_dispatch_intent.side_effect = [RuntimeError("emit failed"), None]
        capacity = make_capacity(remaining=2)
        coordinator = GlobalDispatchCoordinator(capacity, [service])
        install_issue_loader(
            coordinator, {1: IssueState.CLAIMED, 2: IssueState.CLAIMED}
        )
        await coordinator.coordinate()
        assert service._emit_dispatch_intent.call_count == 2

    @pytest.mark.asyncio
    async def test_collect_failure_does_not_affect_other_roles(self) -> None:
        bad_service = make_service("manager", [])
        bad_service.collect_ready_issues = AsyncMock(side_effect=RuntimeError("API"))
        good_service = make_service("planner", [make_issue(10)])
        capacity = make_capacity(remaining=1)
        coordinator = GlobalDispatchCoordinator(capacity, [bad_service, good_service])
        install_issue_loader(coordinator, {10: IssueState.CLAIMED})
        await coordinator.coordinate()
        good_service._emit_dispatch_intent.assert_called_once()

    @pytest.mark.asyncio
    async def test_empty_queue_does_nothing(self) -> None:
        service = make_service("planner", [])
        capacity = make_capacity(remaining=1)
        coordinator = GlobalDispatchCoordinator(capacity, [service])
        install_issue_loader(coordinator, {})
        await coordinator.coordinate()
        service._emit_dispatch_intent.assert_not_called()

    @pytest.mark.asyncio
    async def test_collect_order_prefers_higher_state_roles_first(self) -> None:
        manager_svc = make_service("manager", [make_issue(1)])
        planner_svc = make_service("planner", [make_issue(2)])
        capacity = make_capacity(remaining=2)
        coordinator = GlobalDispatchCoordinator(capacity, [manager_svc, planner_svc])
        install_issue_loader(coordinator, {1: IssueState.READY, 2: IssueState.CLAIMED})
        await coordinator.coordinate()
        planner_svc._emit_dispatch_intent.assert_called_once()
        manager_svc._emit_dispatch_intent.assert_called_once()

    @pytest.mark.asyncio
    async def test_capacity_limit_stops_dispatch(self) -> None:
        review_svc = make_service("review", [make_issue(304)])
        planner_svc = make_service("plan", [make_issue(303)])
        manager_svc = make_service("manager", [make_issue(372)])
        capacity = make_capacity(remaining=2)
        coordinator = GlobalDispatchCoordinator(
            capacity, [manager_svc, planner_svc, review_svc]
        )
        install_issue_loader(
            coordinator,
            {304: IssueState.REVIEW, 303: IssueState.CLAIMED, 372: IssueState.READY},
        )
        await coordinator.coordinate()
        review_dispatched = review_svc._emit_dispatch_intent.call_args.args[0]
        planner_dispatched = planner_svc._emit_dispatch_intent.call_args.args[0]
        assert review_dispatched.number == 304
        assert planner_dispatched.number == 303
        manager_svc._emit_dispatch_intent.assert_not_called()

    @pytest.mark.asyncio
    async def test_state_change_requeues_issue_to_front(self) -> None:
        manager_svc = make_service("manager", [make_issue(1), make_issue(2)])
        planner_svc = make_service("planner", [])
        capacity = make_capacity(remaining=1)
        coordinator = GlobalDispatchCoordinator(capacity, [manager_svc, planner_svc])
        states = {1: IssueState.READY, 2: IssueState.READY}
        install_issue_loader(coordinator, states)
        await coordinator.coordinate()
        first_dispatched = manager_svc._emit_dispatch_intent.call_args.args[0]
        assert first_dispatched.number == 1
        states[1] = IssueState.CLAIMED
        await coordinator.coordinate()
        assert planner_svc._emit_dispatch_intent.call_count == 1
        promoted_issue = planner_svc._emit_dispatch_intent.call_args.args[0]
        assert promoted_issue.number == 1

    @pytest.mark.asyncio
    async def test_terminal_state_removes_issue_from_queue(self) -> None:
        manager_svc = make_service("manager", [make_issue(1)])
        capacity = make_capacity(remaining=1)
        coordinator = GlobalDispatchCoordinator(capacity, [manager_svc])
        states = {1: IssueState.READY}
        install_issue_loader(coordinator, states)
        await coordinator.coordinate()
        states[1] = IssueState.BLOCKED
        await coordinator.coordinate()
        await coordinator.coordinate()
        assert manager_svc._emit_dispatch_intent.call_count == 1

    @pytest.mark.asyncio
    async def test_logs_dispatch_intent_instead_of_dispatch_success(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        planner_svc = make_service("planner", [make_issue(303)])
        capacity = make_capacity(remaining=1)
        coordinator = GlobalDispatchCoordinator(capacity, [planner_svc])
        install_issue_loader(coordinator, {303: IssueState.CLAIMED})
        events: list[str] = []

        def capture_event(_: str, message: str, level: str = "INFO") -> None:
            events.append(message)

        monkeypatch.setattr(
            "vibe3.orchestra.global_dispatch_coordinator.append_orchestra_event",
            capture_event,
        )
        await coordinator.coordinate()
        normalized = [re.sub(r"\x1b\[[0-9;]*m", "", msg) for msg in events]
        assert any("dispatch-intent #303 (planner)" in msg for msg in normalized)
        assert not any("dispatched #303 (planner)" in msg for msg in normalized)

    @pytest.mark.asyncio
    async def test_logs_dispatch_intent_before_emit_side_effect(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        planner_svc = make_service("planner", [make_issue(467)])
        capacity = make_capacity(remaining=1)
        coordinator = GlobalDispatchCoordinator(capacity, [planner_svc])
        install_issue_loader(coordinator, {467: IssueState.CLAIMED})
        events: list[str] = []

        def capture_event(_: str, message: str, level: str = "INFO") -> None:
            events.append(message)

        def emit_side_effect(_: MagicMock) -> None:
            capture_event(
                "dispatcher",
                "planner launch failed for #467: Failed to resolve permanent worktree",
            )

        planner_svc._emit_dispatch_intent.side_effect = emit_side_effect
        monkeypatch.setattr(
            "vibe3.orchestra.global_dispatch_coordinator.append_orchestra_event",
            capture_event,
        )
        await coordinator.coordinate()
        normalized = [re.sub(r"\x1b\[[0-9;]*m", "", msg) for msg in events]
        assert normalized[0] == "GlobalDispatchCoordinator: starting queue collection"
        assert (
            normalized[1]
            == "GlobalDispatchCoordinator: queue collection complete, total=1 issues"
        )
        assert (
            normalized[2] == "GlobalDispatchCoordinator: dispatch-intent #467 (planner)"
        )
        assert (
            normalized[3]
            == "planner launch failed for #467: Failed to resolve permanent worktree"
        )

    @pytest.mark.asyncio
    async def test_queue_persisted_after_dispatch_intent(self) -> None:
        """SQLite contains entry after coordinate() emits dispatch intent."""
        service = make_service("planner", [make_issue(100)])
        capacity = make_capacity(remaining=1)
        store = MagicMock()
        store.load_queue_entries.return_value = []
        coordinator = GlobalDispatchCoordinator(capacity, [service], store=store)
        install_issue_loader(coordinator, {100: IssueState.CLAIMED})
        await coordinator.coordinate()
        store.save_queue_entry.assert_called()
        call_args = store.save_queue_entry.call_args
        assert call_args[1]["issue_number"] == 100
        assert call_args[1]["collected_state"] == "claimed"

    @pytest.mark.asyncio
    async def test_queue_loaded_on_coordinator_init(self) -> None:
        """Entries restored from SQLite on coordinator initialization."""
        store = MagicMock()
        store.load_queue_entries.return_value = [
            {
                "issue_number": 200,
                "collected_state": "in-progress",
                "waiting_state": None,
                "retry_count": 2,
            },
            {
                "issue_number": 201,
                "collected_state": "review",
                "waiting_state": "review",
                "retry_count": 1,
            },
        ]
        service = make_service("planner", [])
        capacity = make_capacity(remaining=1)
        coordinator = GlobalDispatchCoordinator(capacity, [service], store=store)
        assert coordinator._frozen_queue is not None
        assert len(coordinator._frozen_queue) == 2
        assert coordinator._frozen_queue[0].issue_number == 200
        assert coordinator._frozen_queue[0].retry_count == 2
        assert coordinator._frozen_queue[1].issue_number == 201
        assert coordinator._frozen_queue[1].waiting_state == "review"

    @pytest.mark.asyncio
    async def test_entry_removed_after_state_done(self) -> None:
        """SQLite cleanup on terminal state."""
        service = make_service("manager", [make_issue(300)])
        capacity = make_capacity(remaining=1)
        store = MagicMock()
        store.load_queue_entries.return_value = [
            {
                "issue_number": 300,
                "collected_state": "ready",
                "waiting_state": None,
                "retry_count": 0,
            }
        ]
        coordinator = GlobalDispatchCoordinator(capacity, [service], store=store)
        states = {300: IssueState.READY}
        install_issue_loader(coordinator, states)
        await coordinator.coordinate()
        states[300] = IssueState.DONE
        await coordinator.coordinate()
        store.remove_queue_entry.assert_called_with(300)

    @pytest.mark.asyncio
    async def test_retry_threshold_removes_entry(self) -> None:
        """Auto-removal after exceeding MAX_RETRY_COUNT."""
        service = make_service("planner", [])
        capacity = make_capacity(remaining=1)
        store = MagicMock()
        store.load_queue_entries.return_value = [
            {
                "issue_number": 400,
                "collected_state": "claimed",
                "waiting_state": "claimed",
                "retry_count": MAX_RETRY_COUNT + 1,
            }
        ]
        store.get_queue_entries_over_retry_limit.return_value = [400]
        coordinator = GlobalDispatchCoordinator(capacity, [service], store=store)
        install_issue_loader(coordinator, {400: IssueState.CLAIMED})
        await coordinator.coordinate()
        assert coordinator._frozen_queue is not None
        assert 400 not in [e.issue_number for e in coordinator._frozen_queue]
        store.remove_queue_entry.assert_called_with(400)

    @pytest.mark.asyncio
    async def test_server_restart_preserves_queue(self) -> None:
        """Integration: queue survives simulated restart."""
        manager_service = make_service("manager", [make_issue(500)])
        planner_service = make_service("planner", [])
        capacity = make_capacity(remaining=1)
        store = MagicMock()
        store.load_queue_entries.return_value = []
        coordinator1 = GlobalDispatchCoordinator(
            capacity, [manager_service, planner_service], store=store
        )
        install_issue_loader(coordinator1, {500: IssueState.READY})
        await coordinator1.coordinate()
        assert manager_service._emit_dispatch_intent.call_count == 1
        save_call = store.save_queue_entry.call_args
        assert save_call[1]["issue_number"] == 500
        assert save_call[1]["waiting_state"] == "ready"
        store.load_queue_entries.return_value = [
            {
                "issue_number": 500,
                "collected_state": "ready",
                "waiting_state": "ready",
                "retry_count": 1,
            }
        ]
        coordinator2 = GlobalDispatchCoordinator(
            capacity, [manager_service, planner_service], store=store
        )
        install_issue_loader(coordinator2, {500: IssueState.CLAIMED})
        assert coordinator2._frozen_queue is not None
        assert len(coordinator2._frozen_queue) == 1
        assert coordinator2._frozen_queue[0].issue_number == 500
        assert coordinator2._frozen_queue[0].retry_count == 1
        await coordinator2.coordinate()
        assert len(coordinator2._frozen_queue) == 1
        assert coordinator2._frozen_queue[0].waiting_state == "claimed"
        assert coordinator2._frozen_queue[0].retry_count == 0
        assert planner_service._emit_dispatch_intent.call_count == 1
