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


def make_capacity(remaining: int = 1) -> MagicMock:
    """Create mock capacity service with specified remaining slots."""
    capacity = MagicMock()
    capacity.get_capacity_status = MagicMock(
        return_value={
            "remaining": remaining,
            "active_count": 0,
            "max_capacity": 5,
        }
    )
    capacity._registry = MagicMock()
    capacity._registry.get_truly_live_sessions_for_target = MagicMock(return_value=[])
    return capacity


class TestGlobalDispatchCoordinator:

    @pytest.mark.asyncio
    async def test_dispatch_all_when_capacity_available(self) -> None:
        """容量足够时，所有 issues 被 dispatch。"""
        issues = [make_issue(1), make_issue(2)]
        service = make_service("planner", issues)
        capacity = make_capacity(remaining=2)

        coordinator = GlobalDispatchCoordinator(capacity, [service])
        await coordinator.coordinate()

        assert service._emit_dispatch_intent.call_count == 2

    @pytest.mark.asyncio
    async def test_skip_when_capacity_full(self) -> None:
        """容量满时跳过 issue，不 emit，下次 tick 再试。"""
        issues = [make_issue(1), make_issue(2), make_issue(3)]
        service = make_service("planner", issues)
        # 只有 2 个槽位，第 3 个被跳过
        capacity = make_capacity(remaining=2)

        coordinator = GlobalDispatchCoordinator(capacity, [service])
        await coordinator.coordinate()

        assert service._emit_dispatch_intent.call_count == 2

    @pytest.mark.asyncio
    async def test_emit_failure_handled_gracefully(self) -> None:
        """emit 失败时，异常被记录，继续尝试下一个 issue。"""
        issue1 = make_issue(1)
        issue2 = make_issue(2)
        service = make_service("planner", [issue1, issue2])
        # Issue 1 emit 失败，Issue 2 成功
        service._emit_dispatch_intent.side_effect = [
            RuntimeError("emit failed"),
            None,
        ]
        capacity = make_capacity(remaining=2)

        coordinator = GlobalDispatchCoordinator(capacity, [service])
        await coordinator.coordinate()

        # Issue 1 和 Issue 2 都尝试了
        assert service._emit_dispatch_intent.call_count == 2

    @pytest.mark.asyncio
    async def test_collect_failure_does_not_affect_other_services(self) -> None:
        """某 service collect 失败，其他 service 正常继续。"""
        issue_planner = make_issue(10)
        bad_service = make_service("manager", [])
        bad_service.collect_ready_issues = AsyncMock(
            side_effect=RuntimeError("API error")
        )
        good_service = make_service("planner", [issue_planner])
        capacity = make_capacity(remaining=1)

        coordinator = GlobalDispatchCoordinator(capacity, [bad_service, good_service])
        await coordinator.coordinate()

        good_service._emit_dispatch_intent.assert_called_once()

    @pytest.mark.asyncio
    async def test_empty_pool_does_nothing(self) -> None:
        """无 ready issues 时，coordinator 静默退出。"""
        service = make_service("planner", [])
        capacity = make_capacity(remaining=0)

        coordinator = GlobalDispatchCoordinator(capacity, [service])
        await coordinator.coordinate()

        # 没有 issue 被 dispatch
        service._emit_dispatch_intent.assert_not_called()

    @pytest.mark.asyncio
    async def test_fixed_role_order_dispatch(self) -> None:
        """固定 role 顺序派发：reviewer → executor → planner → manager。"""
        manager_issue = make_issue(1)
        planner_issue = make_issue(2)
        manager_svc = make_service("manager", [manager_issue])
        planner_svc = make_service("planner", [planner_issue])
        capacity = make_capacity(remaining=2)

        coordinator = GlobalDispatchCoordinator(capacity, [manager_svc, planner_svc])
        await coordinator.coordinate()

        # planner 先派发（reviewer/executor 没有 issue）
        planner_svc._emit_dispatch_intent.assert_called_once()
        manager_svc._emit_dispatch_intent.assert_called_once()

    @pytest.mark.asyncio
    async def test_skip_issue_with_live_session(self) -> None:
        """已有 live session 的 issue 被跳过，不重复派发。"""
        issues = [make_issue(1), make_issue(2)]
        service = make_service("planner", issues)
        capacity = make_capacity(remaining=2)
        # Issue 1 已有 live session
        capacity._registry.get_truly_live_sessions_for_target = MagicMock(
            side_effect=lambda role, branch, target_id: (
                [{"id": 1}] if target_id == "1" else []
            )
        )

        coordinator = GlobalDispatchCoordinator(capacity, [service])
        await coordinator.coordinate()

        # Issue 1 被跳过，Issue 2 dispatched
        assert service._emit_dispatch_intent.call_count == 1
        assert service._emit_dispatch_intent.call_args[0][0].number == 2

    @pytest.mark.asyncio
    async def test_dispatch_by_fixed_role_order_with_multiple_roles(self) -> None:
        """多个 role 有 issue 时，按固定顺序派发。"""
        review_issue = make_issue(304)
        planner_issue = make_issue(303)
        manager_issue = make_issue(372)
        review_svc = make_service("review", [review_issue])
        planner_svc = make_service("plan", [planner_issue])
        manager_svc = make_service("manager", [manager_issue])
        capacity = make_capacity(remaining=3)

        coordinator = GlobalDispatchCoordinator(
            capacity, [manager_svc, planner_svc, review_svc]
        )
        await coordinator.coordinate()

        # reviewer → executor → planner → manager
        review_svc._emit_dispatch_intent.assert_called_once_with(review_issue)
        planner_svc._emit_dispatch_intent.assert_called_once_with(planner_issue)
        manager_svc._emit_dispatch_intent.assert_called_once_with(manager_issue)

    @pytest.mark.asyncio
    async def test_capacity_limit_stops_dispatch(self) -> None:
        """容量不足时停止派发，即使还有更多 issue。"""
        review_issue = make_issue(304)
        planner_issue = make_issue(303)
        manager_issue = make_issue(372)
        review_svc = make_service("review", [review_issue])
        planner_svc = make_service("plan", [planner_issue])
        manager_svc = make_service("manager", [manager_issue])
        capacity = make_capacity(remaining=2)  # 只能派发 2 个

        coordinator = GlobalDispatchCoordinator(
            capacity, [manager_svc, planner_svc, review_svc]
        )
        await coordinator.coordinate()

        # reviewer 和 planner 派发，manager 被跳过
        review_svc._emit_dispatch_intent.assert_called_once_with(review_issue)
        planner_svc._emit_dispatch_intent.assert_called_once_with(planner_issue)
        manager_svc._emit_dispatch_intent.assert_not_called()
