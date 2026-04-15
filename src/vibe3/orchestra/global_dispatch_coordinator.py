"""全局调度协调器：统一收集、排序、容量拦截后再 dispatch。

解决问题：
  - dispatch_intent 在容量检查前发出 → 多余 issue 卡在 state/claimed
  - manager 速度远超 planner → backlog 持续增长
  - 各 service 独立扫描 → 无法全局排序

设计原则：
  - collect: 并行，无副作用
  - sort: 全局，按 milestone/roadmap/priority
  - dispatch: 顺序，check → mark_in_flight → emit（同一 asyncio 事件循环，天然原子）
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

from loguru import logger

from vibe3.execution.capacity_service import CapacityService
from vibe3.models.orchestration import IssueInfo
from vibe3.orchestra.logging import append_orchestra_event
from vibe3.orchestra.queue_ordering import (
    PIPELINE_STAGE_DEFAULT,
    PIPELINE_STAGE_ORDER,
)

if TYPE_CHECKING:
    from vibe3.orchestra.services.state_label_dispatch import StateLabelDispatchService


@dataclass
class ReadyIssueWithRole:
    """Issue + 对应的 dispatch service（含 role 信息）。"""

    issue: IssueInfo
    service: StateLabelDispatchService

    @property
    def role(self) -> str:
        # Use registry_role ("planner"/"executor"/"reviewer") not trigger_name
        # ("plan"/"run"/"review") so CapacityService queries SQLite with the
        # same role name that sessions are stored under.
        return str(self.service.role_def.registry_role)


class GlobalDispatchCoordinator:
    """统一调度协调器。

    取代 OrchestrationFacade 中的并发 gather(service.on_tick())，
    实现"先检查容量，再 emit dispatch_intent"。

    Usage:
        coordinator = GlobalDispatchCoordinator(capacity_service, dispatch_services)
        await coordinator.coordinate()
    """

    def __init__(
        self,
        capacity: CapacityService,
        dispatch_services: list[StateLabelDispatchService],
    ) -> None:
        self._capacity = capacity
        self._dispatch_services = dispatch_services

    async def coordinate(self) -> None:
        """主调度入口：收集 → 排序 → 容量拦截 → dispatch。"""
        # Step 0: 把上一轮成功 dispatch 但已注册为 live session 的 in-flight
        # 条目清理掉，防止 in-flight 永久积压导致容量计算双重扣减（deadlock）。
        self._capacity.reconcile_in_flight()

        # Step 1: 并行收集所有角色的 ready issues（无副作用）
        all_ready = await self._collect_all(self._dispatch_services)

        if not all_ready:
            return

        # Step 2: 全局排序（复用 sort_ready_issues，按 issue 优先级排序）
        # 注意：不同角色的 issue 在 pipeline 不同阶段，不直接竞争
        # 排序目的是：同一角色内按优先级选出最重要的先 dispatch
        sorted_ready = self._sort_with_role(all_ready)

        # Step 3: 顺序尝试 dispatch（asyncio 单线程，check-mark-emit 天然原子）
        dispatched_count = 0
        skipped_count = 0
        for item in sorted_ready:
            dispatched = self._try_dispatch(item)
            if dispatched:
                dispatched_count += 1
            else:
                skipped_count += 1

        append_orchestra_event(
            "dispatcher",
            f"GlobalDispatchCoordinator: dispatched={dispatched_count} "
            f"skipped={skipped_count} (capacity full)",
        )

    async def _collect_all(
        self, services: list[StateLabelDispatchService]
    ) -> list[ReadyIssueWithRole]:
        """并行调用所有 service 的 collect_ready_issues()。"""
        results = await asyncio.gather(
            *(svc.collect_ready_issues() for svc in services),
            return_exceptions=True,
        )
        all_ready: list[ReadyIssueWithRole] = []
        for service, result in zip(services, results, strict=False):
            if isinstance(result, BaseException):
                logger.bind(
                    domain="global_dispatch",
                    service=service.service_name,
                ).error(f"collect_ready_issues failed: {result}")
                continue
            # result is now guaranteed to be list[IssueInfo]
            for issue in result:
                all_ready.append(ReadyIssueWithRole(issue=issue, service=service))
        return all_ready

    def _sort_with_role(
        self, items: list[ReadyIssueWithRole]
    ) -> list[ReadyIssueWithRole]:
        """Sort cross-role ready items by pipeline stage first, then issue priority.

        Primary key: pipeline stage so issues deep in pipeline dispatch first:
            review → run → plan → manager:handoff → manager:ready
        Secondary key: standard issue priority (milestone / roadmap / priority label).
        """
        from vibe3.orchestra.queue_ordering import (
            resolve_milestone_rank,
            resolve_priority,
            resolve_roadmap_rank,
        )

        def sort_key(item: ReadyIssueWithRole) -> tuple[int, int, int, int, int]:
            # Pipeline stage: lower = higher dispatch priority
            trigger_name = item.service.role_def.trigger_name
            trigger_state = item.service.role_def.trigger_state.value
            stage_tag = f"{trigger_name}:{trigger_state}"
            stage = PIPELINE_STAGE_ORDER.get(stage_tag, PIPELINE_STAGE_DEFAULT)

            # Within the same stage, reuse existing issue-level ordering
            issue = item.issue
            milestone_dict = (
                {"title": issue.milestone, "number": 0} if issue.milestone else None
            )
            milestone_rank, _ = resolve_milestone_rank(milestone_dict)
            roadmap_rank, _ = resolve_roadmap_rank(issue.labels)
            priority = resolve_priority(issue.labels)

            return (stage, milestone_rank, roadmap_rank, -priority, issue.number)

        return sorted(items, key=sort_key)

    def _try_dispatch(self, item: ReadyIssueWithRole) -> bool:
        """容量检查 → 标记 in_flight → emit dispatch_intent。

        在同一个 asyncio 事件循环的同步代码段内执行，天然原子：
        没有 await，不会被其他协程中断。

        Returns:
            True 如果成功 dispatch，False 如果容量满跳过
        """
        role = item.role
        issue_id = item.issue.number

        # 容量检查（在 emit 之前）
        if not self._capacity.can_dispatch(role, issue_id):
            append_orchestra_event(
                "dispatcher",
                f"GlobalDispatchCoordinator: skipped #{issue_id} "
                f"({role}) - capacity full",
                level="DEBUG",
            )
            logger.bind(
                domain="global_dispatch",
                role=role,
                issue=issue_id,
            ).debug(f"Skip #{issue_id} ({role}): capacity full, will retry next tick")
            return False

        # 先标记 in_flight，再 emit（保证 coordinator 后续检查也会看到）
        try:
            self._capacity.mark_in_flight(role, issue_id)
        except Exception as exc:
            logger.bind(domain="global_dispatch", role=role, issue=issue_id).error(
                f"mark_in_flight failed for #{issue_id}: {exc}"
            )
            return False

        try:
            item.service._emit_dispatch_intent(item.issue)
            append_orchestra_event(
                "dispatcher",
                f"GlobalDispatchCoordinator: dispatched #{issue_id} ({role})",
            )
            logger.bind(
                domain="global_dispatch",
                role=role,
                issue=issue_id,
            ).info(f"✅ Dispatched #{issue_id} ({role})")
            # ✅ emit 成功后保留 in-flight 标记
            # 等待 session 注册到 SQLite 后，由 reconcile_in_flight 在下一 tick 清理
            # 这样才能正确占用容量，防止超额派发
            return True
        except Exception as exc:
            # emit 失败时撤销 in_flight 标记，避免永久占用容量
            self._capacity.prune_in_flight(role, {issue_id})
            logger.bind(
                domain="global_dispatch",
                role=role,
                issue=issue_id,
            ).error(f"emit_dispatch_intent failed for #{issue_id}: {exc}")
            append_orchestra_event(
                "dispatcher",
                f"GlobalDispatchCoordinator: emit failed for "
                f"#{issue_id} ({role}): {exc}",
            )
            return False
