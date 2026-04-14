"""Tests for GlobalDispatchCoordinator."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from vibe3.orchestra.global_dispatch_coordinator import (
    GlobalDispatchCoordinator,
)


def make_issue(number: int, priority: int = 5) -> MagicMock:
    issue = MagicMock()
    issue.number = number
    issue.labels = [f"priority/{priority}"]
    issue.milestone = None
    return issue


def make_service(role: str, ready_issues: list) -> MagicMock:
    service = MagicMock()
    service.service_name = f"mock-{role}"
    service.role_def.trigger_name = role
    service.collect_ready_issues = AsyncMock(return_value=ready_issues)
    service._emit_dispatch_intent = MagicMock()
    return service


def make_capacity(can_dispatch_results: list[bool]) -> MagicMock:
    capacity = MagicMock()
    capacity.can_dispatch = MagicMock(side_effect=can_dispatch_results)
    capacity.mark_in_flight = MagicMock()
    capacity.prune_in_flight = MagicMock()
    return capacity


class TestGlobalDispatchCoordinator:

    @pytest.mark.asyncio
    async def test_dispatch_all_when_capacity_available(self) -> None:
        """容量足够时，所有 issues 被 dispatch。"""
        issues = [make_issue(1), make_issue(2)]
        service = make_service("planner", issues)
        capacity = make_capacity([True, True])

        coordinator = GlobalDispatchCoordinator(capacity, [service])
        await coordinator.coordinate()

        assert service._emit_dispatch_intent.call_count == 2
        assert capacity.mark_in_flight.call_count == 2

    @pytest.mark.asyncio
    async def test_skip_when_capacity_full(self) -> None:
        """容量满时跳过 issue，不 emit，下次 tick 再试。"""
        issues = [make_issue(1), make_issue(2), make_issue(3)]
        service = make_service("planner", issues)
        # 前 2 个成功，第 3 个容量满
        capacity = make_capacity([True, True, False])

        coordinator = GlobalDispatchCoordinator(capacity, [service])
        await coordinator.coordinate()

        assert service._emit_dispatch_intent.call_count == 2
        assert capacity.mark_in_flight.call_count == 2

    @pytest.mark.asyncio
    async def test_emit_failure_prunes_in_flight(self) -> None:
        """emit 失败时，in_flight 标记被自动撤销，避免容量泄漏。"""
        issue = make_issue(1)
        service = make_service("planner", [issue])
        service._emit_dispatch_intent.side_effect = RuntimeError("emit failed")
        capacity = make_capacity([True])

        coordinator = GlobalDispatchCoordinator(capacity, [service])
        await coordinator.coordinate()

        capacity.mark_in_flight.assert_called_once_with("planner", 1)
        capacity.prune_in_flight.assert_called_once_with("planner", {1})

    @pytest.mark.asyncio
    async def test_collect_failure_does_not_affect_other_services(self) -> None:
        """某 service collect 失败，其他 service 正常继续。"""
        issue_planner = make_issue(10)
        bad_service = make_service("manager", [])
        bad_service.collect_ready_issues = AsyncMock(
            side_effect=RuntimeError("API error")
        )
        good_service = make_service("planner", [issue_planner])
        capacity = make_capacity([True])

        coordinator = GlobalDispatchCoordinator(capacity, [bad_service, good_service])
        await coordinator.coordinate()

        good_service._emit_dispatch_intent.assert_called_once()

    @pytest.mark.asyncio
    async def test_empty_pool_does_nothing(self) -> None:
        """无 ready issues 时，coordinator 静默退出，不调用容量检查。"""
        service = make_service("planner", [])
        capacity = make_capacity([])

        coordinator = GlobalDispatchCoordinator(capacity, [service])
        await coordinator.coordinate()

        capacity.can_dispatch.assert_not_called()

    @pytest.mark.asyncio
    async def test_cross_role_issues_both_dispatched(self) -> None:
        """manager 和 planner 各有 issues，各自独立 dispatch。"""
        manager_issue = make_issue(1)
        planner_issue = make_issue(2)
        manager_svc = make_service("manager", [manager_issue])
        planner_svc = make_service("planner", [planner_issue])
        capacity = make_capacity([True, True])

        coordinator = GlobalDispatchCoordinator(capacity, [manager_svc, planner_svc])
        await coordinator.coordinate()

        manager_svc._emit_dispatch_intent.assert_called_once()
        planner_svc._emit_dispatch_intent.assert_called_once()

    @pytest.mark.asyncio
    async def test_mark_in_flight_before_emit(self) -> None:
        """mark_in_flight 必须在 emit 之前调用（check-mark-emit 顺序）。"""
        call_order: list[str] = []
        issue = make_issue(1)
        service = make_service("planner", [issue])

        capacity = MagicMock()
        capacity.can_dispatch = MagicMock(return_value=True)
        capacity.mark_in_flight = MagicMock(
            side_effect=lambda *_: call_order.append("mark")
        )
        service._emit_dispatch_intent = MagicMock(
            side_effect=lambda *_: call_order.append("emit")
        )

        coordinator = GlobalDispatchCoordinator(capacity, [service])
        await coordinator.coordinate()

        assert call_order == [
            "mark",
            "emit",
        ], f"Expected mark before emit, got: {call_order}"
