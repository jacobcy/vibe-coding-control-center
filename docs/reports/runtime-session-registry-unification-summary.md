# Runtime Session Registry Unification - Completion Summary

> **Date**: 2026-04-07
> **Branch**: dev/issue-451
> **Plan**: [docs/plans/2026-04-07-runtime-session-registry-unification-plan.md](../plans/2026-04-07-runtime-session-registry-unification-plan.md)

## 执行概况

Runtime Session Registry 统一迁移已完成所有 6 个任务，实现了用单一 `runtime_session` registry 统一 manager、dispatcher、governance 以及 plan/run/review 的异步 session 命名、探活、计数、持久化与展示规则。

## 完成的任务

### Task 1: 定义 Runtime Session 领域模型与 SQLite 真源

- Commit: `ccc9b7d3 feat: add runtime session registry store`
- 创建 `runtime_session` 表和 CRUD 操作
- 字段覆盖所有五类角色（manager/planner/executor/reviewer/governance）
- 状态枚举支持 starting/running/done/failed/aborted/orphaned

### Task 2: 收口命名、探活、计数为 SessionRegistryService

- Commit: `76b1903a refactor: centralize runtime session semantics`
- 创建 `SessionRegistryService` 统一管理 reserve/mark_started/mark_finished/count_live_worker_sessions/reconcile_live_state
- 收口命名函数为 `build_session_name(role, target_type, target_id)`
- 计数口径统一：只算 registry 中 starting/running 且探活成功的 worker session

### Task 3: 先切 manager 与 dispatcher 的容量和探活

- Commit: `390567c9 refactor: use runtime session registry for manager capacity`
- `manager_executor.py` 使用 registry 的 `count_live_worker_sessions(role="manager")`
- `state_label_dispatch.py` 的 `_has_live_dispatch()` 改用 registry
- 兼容镜像保留：`manager_session_id` 字段继续写入，避免打断现有读路径

### Task 4: 切 plan / run / review 生命周期到 registry

- Commit: `85c56edf refactor: route plan/run/review sessions through registry`
- `execution_lifecycle.py` 成为 planner/executor/reviewer 与 registry 的统一桥
- started/completed/aborted 三种事件同时更新 registry 与兼容镜像
- Authoritative ref gate 语义保持不变，只迁 session 真源

### Task 5: 切 governance 到同一 session 语义

- Commit: `9e652f90 refactor: unify governance sessions with registry`
- `governance_service.py` 不再把 `_in_flight` 当最终真源，只当本 tick 短期防抖
- 是否存在 live governance worker，统一由 registry 判断
- `_in_flight` 只剩本进程防抖职责，不再兼职 session 真源

### Task 6: 清理兼容层，收口文档和状态展示

- Commit: `65882b46 docs: finalize runtime session registry migration`
- `flow.py` 的 session_id 字段标记 `[Deprecated] Use runtime_session registry instead`
- `handoff_read.py` 优先展示 registry live sessions，旧字段只做 fallback
- Orchestra capacity throttling 使用 registry（修复 code review 发现的关键问题）
- `task_resume_usecase.py` 查询 registry 判断是否有 live sessions
- 文档更新：README.md 和 DEVELOPMENT.md 添加 registry-based capacity throttling 说明

## 成功判据验证

✅ **1. manager、dispatcher、governance、plan、run、review 的异步 session 都能在同一 registry 中看到**

- 所有角色的 session 创建、更新、结束都通过 `execution_lifecycle.py` 或直接调用 `SessionRegistryService` 写入 registry
- `runtime_session` 表包含 role 字段，支持五类角色过滤查询

✅ **2. 容量限制只看 live worker session，不看 active flow，不看服务自身 tmux**

- `SessionRegistryService.count_live_worker_sessions()` 只算 status=starting/running 且探活成功的 session
- `manager_executor.py`、`state_label_dispatch.py`（容量 throttle）都使用此方法
- 旧的 `get_active_manager_session_count()` 已标记 deprecated，仅作 fallback

✅ **3. orchestration log 能明确区分 dispatched、running、throttled、deferred、orphaned**

- `state_label_dispatch.py` 的日志明确区分 throttled（容量限制）和 deferred（其他原因）
- Registry 的 status 字段支持 orphaned 状态，用于标记探活失败但 registry 中仍存在的 session

✅ **4. handoff/status/read 路径不再把旧的 role_session_id 字段当唯一真源**

- `handoff_read.py` 的 `_get_live_sessions_for_branch()` 查询 registry
- `task_resume_usecase.py` 查询 registry 判断 has_live_sessions
- 所有读侧优先使用 registry 结果，旧字段只做 fallback

✅ **5. authoritative ref gate 语义保持不变，没有和 session registry 交叉污染**

- Task 4 明确保持 authoritative ref gate 不动，只迁 session 真源
- `review_agent.py` 返回的 authoritative audit 路径逻辑不变

## 测试覆盖

- **单元测试**：每个 task 都有对应的 pytest 测试文件
- **回归测试**：Task 6 最后运行 70 个相关测试全部通过
- **集成测试**：
  - `test_session_registry.py` - registry 服务逻辑
  - `test_manager_executor.py::TestManagerExecutorRegistryCapacity` - manager 容量使用 registry
  - `test_state_label_dispatch_capacity.py` - orchestra throttle 使用 registry
  - `test_governance_service.py` - governance 使用 registry
  - `test_execution_lifecycle.py` - plan/run/review 生命周期写入 registry

## Code Review

- **Task 6 Review**：使用 `code-reviewer` agent，发现并修复关键问题（orchestra capacity bypass registry）
- **修复后验证**：再次运行测试和 ruff check 全部通过
- **文档一致性**：README.md 和 DEVELOPMENT.md 的说明与代码实现完全一致

## 关键改进

1. **统一真源**：不再有多个分散的 session 真源（flow_state 字段、tmux prefix、governance in-flight）
2. **准确容量**：容量 throttle 基于 live worker session，不再误算 active flow 或服务自身 tmux
3. **清晰语义**：registry 明确区分 starting/running/done/failed/aborted/orphaned
4. **兼容 fallback**：读侧优先 registry，旧字段仅作 fallback，不破坏现有 handoff/status 功能
5. **可扩展性**：新增角色只需在 registry 中添加 role，无需修改字段或探活逻辑

## 后续建议

1. **监控 registry 数据**：定期检查 `runtime_session` 表，确保探活逻辑正常清理 dead sessions
2. **逐步移除 deprecated 字段**：待所有读侧完全迁移到 registry 后，可考虑移除 flow_state 的 session_id 字段
3. **增强探活机制**：可考虑增加 heartbeat 或定期 reconcile，自动清理长时间未探活的 orphaned sessions
4. **统一展示层**：所有 UI 展示（status、flow show）统一从 registry 派生 session 视图

## 文档更新

- [README.md](../../README.md) - 添加 registry-based capacity throttling 原则
- [docs/DEVELOPMENT.md](../DEVELOPMENT.md) - 添加 runtime session registry key concept
- 本文档：docs/reports/runtime-session-registry-unification-summary.md

## 相关文档

- [Plan](../plans/2026-04-07-runtime-session-registry-unification-plan.md)
- [Glossary](../standards/glossary.md) - runtime_session、registry、worker session 等术语定义