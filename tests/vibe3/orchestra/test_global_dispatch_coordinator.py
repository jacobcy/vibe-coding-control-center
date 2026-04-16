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
    role_map = {
        "manager": ("manager", "manager", "ready"),
        "planner": ("plan", "planner", "claimed"),
        "plan": ("plan", "planner", "claimed"),
        "executor": ("run", "executor", "in-progress"),
        "run": ("run", "executor", "in-progress"),
        "reviewer": ("review", "reviewer", "review"),
        "review": ("review", "reviewer", "review"),
    }
    trigger_name, registry_role, trigger_state = role_map.get(
        role, ("manager", role, "ready")
    )
    service.role_def.trigger_name = trigger_name
    service.role_def.registry_role = registry_role
    service.role_def.trigger_state.value = trigger_state
    service.collect_ready_issues = AsyncMock(return_value=ready_issues)
    service._emit_dispatch_intent = MagicMock()
    return service


def make_capacity(can_dispatch_results: list[bool]) -> MagicMock:
    capacity = MagicMock()
    capacity.can_dispatch = MagicMock(side_effect=can_dispatch_results)
    capacity.is_in_flight = MagicMock(return_value=False)  # Not in-flight by default
    capacity.mark_in_flight = MagicMock()
    capacity.prune_in_flight = MagicMock()
    capacity.reconcile_in_flight = MagicMock()
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
    async def test_deeper_pipeline_stage_dispatches_before_manager_ready(self) -> None:
        """有 planner backlog 时，不再继续放行 manager:ready 新入口。"""
        manager_issue = make_issue(1)
        planner_issue = make_issue(2)
        manager_svc = make_service("manager", [manager_issue])
        planner_svc = make_service("planner", [planner_issue])
        capacity = make_capacity([True])

        coordinator = GlobalDispatchCoordinator(capacity, [manager_svc, planner_svc])
        await coordinator.coordinate()

        planner_svc._emit_dispatch_intent.assert_called_once()
        manager_svc._emit_dispatch_intent.assert_not_called()

    @pytest.mark.asyncio
    async def test_review_backlog_blocks_upstream_dispatch(self) -> None:
        """存在 review backlog 时，不应继续派发 planner/manager 新工作。"""
        review_issue = make_issue(304)
        planner_issue = make_issue(303)
        manager_issue = make_issue(372)
        review_svc = make_service("review", [review_issue])
        planner_svc = make_service("plan", [planner_issue])
        manager_svc = make_service("manager", [manager_issue])
        capacity = make_capacity([True])

        coordinator = GlobalDispatchCoordinator(
            capacity, [manager_svc, planner_svc, review_svc]
        )
        await coordinator.coordinate()

        review_svc._emit_dispatch_intent.assert_called_once_with(review_issue)
        planner_svc._emit_dispatch_intent.assert_not_called()
        manager_svc._emit_dispatch_intent.assert_not_called()
        capacity.mark_in_flight.assert_called_once_with("reviewer", 304)

    @pytest.mark.asyncio
    async def test_run_backlog_blocks_plan_and_manager_dispatch(self) -> None:
        """当 run backlog 存在时，只允许 run 继续推进。"""
        run_issue = make_issue(323)
        planner_issue = make_issue(320)
        manager_issue = make_issue(372)
        run_svc = make_service("run", [run_issue])
        planner_svc = make_service("plan", [planner_issue])
        manager_svc = make_service("manager", [manager_issue])
        capacity = make_capacity([True])

        coordinator = GlobalDispatchCoordinator(
            capacity, [manager_svc, planner_svc, run_svc]
        )
        await coordinator.coordinate()

        run_svc._emit_dispatch_intent.assert_called_once_with(run_issue)
        planner_svc._emit_dispatch_intent.assert_not_called()
        manager_svc._emit_dispatch_intent.assert_not_called()

    @pytest.mark.asyncio
    async def test_mark_in_flight_before_emit(self) -> None:
        """mark_in_flight 必须在 emit 之前调用（check-mark-emit 顺序）。"""
        call_order: list[str] = []
        issue = make_issue(1)
        service = make_service("planner", [issue])

        capacity = MagicMock()
        capacity.can_dispatch = MagicMock(return_value=True)
        capacity.is_in_flight = MagicMock(return_value=False)  # Not in-flight
        capacity.reconcile_in_flight = MagicMock()  # Required by coordinate()
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

    @pytest.mark.asyncio
    async def test_reconcile_in_flight_called_before_collect(self) -> None:
        """coordinate() 每次调用都先 reconcile，再 collect，防止 in-flight 永久积压。"""
        call_order: list[str] = []
        issue = make_issue(1)

        service = make_service("planner", [issue])
        original_collect = service.collect_ready_issues

        async def tracked_collect() -> list:
            call_order.append("collect")
            return await original_collect()

        service.collect_ready_issues = tracked_collect

        capacity = MagicMock()
        capacity.can_dispatch = MagicMock(return_value=True)
        capacity.mark_in_flight = MagicMock()
        capacity.prune_in_flight = MagicMock()
        capacity.reconcile_in_flight = MagicMock(
            side_effect=lambda: call_order.append("reconcile")
        )

        coordinator = GlobalDispatchCoordinator(capacity, [service])
        await coordinator.coordinate()

        assert (
            call_order[0] == "reconcile"
        ), f"reconcile_in_flight must be called first, got: {call_order}"
        assert "collect" in call_order
