# Plan: Orchestra 模块拆分 — 提取 Dispatcher 与 Manager

## TL;DR

将 `orchestra/` 拆为三个职责明确的模块：**orchestra**（状态机 + 治理）、**manager**（执行现场管理）、**dispatcher**（纯 agent launcher）。核心动机：解决 worktree 回收无主、职责混合、命名语义过载。

---

## 当前结构问题

| 问题                      | 根因                                                     |
| ------------------------- | -------------------------------------------------------- |
| worktree 回收悬空         | 创建在 dispatcher，声称由 governance 回收，但无代码落地  |
| orchestra 语义过载        | 又是"状态机/治理"，又是"执行基础设施"                    |
| FlowOrchestrator 位置尴尬 | 属于 manager 职责（flow+branch 管理），却放在 orchestra/ |
| dispatcher 职责过宽       | 环境解析 + 执行 + 结果处理，跨了两个抽象层               |
| 测试目录扁平              | 23 个测试文件全在 tests/vibe3/orchestra/，拆分后需重组   |

---

## 目标架构

```
三层职责模型：

Orchestra（状态机 + 治理层）
  "issue 应该进入什么状态？"
  - GovernanceService（AI 分析 → 改标签）
  - StateLabelDispatchService（检测 state/ready → 通知 Manager）
  - AssigneeDispatchService（检测 assigned → 通知 Manager）
  - StatusService（只读聚合）
  - HeartbeatServer + EventBus（事件循环）
  - config.py（全局配置）

Manager（执行现场管理层）
  "为这个任务准备好环境，执行完回收"
  - FlowManager（原 FlowOrchestrator，flow 生命周期）
  - WorktreeManager（原 WorktreeResolverMixin + 回收逻辑）
  - ManagerExecutor（组合 flow + worktree + dispatcher 的编排）
  - ResultHandler（执行后的标签/事件记录）
  - CommandBuilder（命令构造）

Dispatcher（纯 agent launcher）
  "在给定路径启动给定命令"
  - executor.py（subprocess with timeout）
  - circuit_breaker.py（故障保护）
```

---

## 目标目录结构

```
src/vibe3/
  orchestra/                       ← 精简：状态机 + 治理
    __init__.py                    ← 更新 exports
    config.py                      ← 不动（全局配置，三层共用）
    heartbeat.py                   ← 不动
    event_bus.py                   ← 不动
    master.py                      ← 不动（triage AI agent）
    master_handler.py              ← 不动
    dependency_checker.py          ← 不动
    services/
      __init__.py
      assignee_dispatch.py         ← 改：调用 manager 而非 dispatcher
      state_label_dispatch.py      ← 改：调用 manager 而非 dispatcher
      pr_review_dispatch.py        ← 改：调用 manager 而非 dispatcher
      governance_service.py        ← 不动（已经正确）
      comment_reply.py             ← 不动
      status_service.py            ← 不动

  manager/                         ← 新建：执行现场管理
    __init__.py
    flow_manager.py                ← 来自 orchestra/flow_orchestrator.py
    worktree_manager.py            ← 来自 orchestra/dispatcher_worktree.py + 回收逻辑
    manager_executor.py            ← 新建：组合 flow + worktree + dispatch
    result_handler.py              ← 来自 orchestra/result_handler.py
    command_builder.py             ← 来自 orchestra/command_builder.py
    prompts.py                     ← 来自 orchestra/prompts.py

  dispatcher/                      ← 新建：纯 agent launcher
    __init__.py
    executor.py                    ← 来自 orchestra/executor.py
    circuit_breaker.py             ← 来自 orchestra/circuit_breaker.py

  server/                          ← 已存在，更新 imports
    registry.py                    ← 改：引用新模块路径
    app.py                         ← 不动
    mcp.py                         ← 不动
```

---

## 分步实施

### Phase 1: 创建 dispatcher/ 模块（纯移动，零逻辑改动）

**目标**：把纯执行基础设施提取到独立模块

**步骤**：
1. 创建 `src/vibe3/dispatcher/__init__.py`
2. 移动 `orchestra/executor.py` → `dispatcher/executor.py`
3. 移动 `orchestra/circuit_breaker.py` → `dispatcher/circuit_breaker.py`
4. 在原位置留 shim（`from vibe3.dispatcher.executor import run_command`）
5. 更新 `orchestra/dispatcher.py` 中的 import
6. 更新 `tests/vibe3/orchestra/test_circuit_breaker.py` 和 `test_dispatcher_error_category.py` 的 import

**验证**：`uv run pytest tests/vibe3/orchestra/test_circuit_breaker.py tests/vibe3/orchestra/test_dispatcher_error_category.py -v`

**文件变更**：
- `src/vibe3/dispatcher/__init__.py` — 新建
- `src/vibe3/dispatcher/executor.py` — 来自 `orchestra/executor.py`
- `src/vibe3/dispatcher/circuit_breaker.py` — 来自 `orchestra/circuit_breaker.py`
- `src/vibe3/orchestra/executor.py` — 改为 shim
- `src/vibe3/orchestra/circuit_breaker.py` — 改为 shim

*parallel with nothing — 无依赖，第一步*

---

### Phase 2: 创建 manager/ 模块（核心重构）

**目标**：把 flow+worktree+命令构造+结果处理 统一到 manager

**步骤**：
1. 创建 `src/vibe3/manager/__init__.py`
2. 移动并重命名：
   - `orchestra/flow_orchestrator.py` → `manager/flow_manager.py`（类名：`FlowOrchestrator` → `FlowManager`）
   - `orchestra/dispatcher_worktree.py` → `manager/worktree_manager.py`（Mixin → 独立类 `WorktreeManager`）
   - `orchestra/result_handler.py` → `manager/result_handler.py`
   - `orchestra/command_builder.py` → `manager/command_builder.py`
   - `orchestra/prompts.py` → `manager/prompts.py`
3. 在原位置留 shim（保持向后兼容）
4. 新建 `manager/manager_executor.py`：统一编排入口

`ManagerExecutor` 核心接口：
```
class ManagerExecutor:
    """统一的执行现场管理：flow 创建 → worktree 准备 → agent 启动 → 结果处理 → worktree 回收"""

    def dispatch_manager(issue) -> bool
        # 1. flow_manager.create_or_get_flow(issue)
        # 2. worktree_manager.ensure_worktree(issue, branch)
        # 3. command_builder.build_manager_command(issue)
        # 4. dispatcher.execute(cmd, cwd)
        # 5. result_handler.handle(result)
        # 6. worktree_manager.maybe_recycle(cwd, is_temporary)

    def dispatch_review(pr_number) -> bool
    def can_dispatch() -> bool
```

5. **关键新增：worktree 回收逻辑**
   - `worktree_manager.recycle(path)` — git worktree remove
   - `manager_executor.dispatch_manager()` 的 finally 块中有条件回收
   - `_should_recycle()` 检查 flow_status 是否 done/aborted

6. 更新 orchestra/services/ 中的三个 dispatch service：
   - `assignee_dispatch.py`：`self._dispatcher` → `self._manager`
   - `state_label_dispatch.py`：同上
   - `pr_review_dispatch.py`：同上

**验证**：
- `uv run pytest tests/vibe3/orchestra/ -v`（通过 shim 向后兼容）
- `uv run mypy src/vibe3/manager/`

**文件变更**：
- `src/vibe3/manager/__init__.py` — 新建
- `src/vibe3/manager/flow_manager.py` — 来自 `orchestra/flow_orchestrator.py`
- `src/vibe3/manager/worktree_manager.py` — 来自 `orchestra/dispatcher_worktree.py` + 回收
- `src/vibe3/manager/manager_executor.py` — 新建
- `src/vibe3/manager/result_handler.py` — 来自 `orchestra/result_handler.py`
- `src/vibe3/manager/command_builder.py` — 来自 `orchestra/command_builder.py`
- `src/vibe3/manager/prompts.py` — 来自 `orchestra/prompts.py`
- `src/vibe3/orchestra/flow_orchestrator.py` — 改为 shim
- `src/vibe3/orchestra/dispatcher_worktree.py` — 改为 shim
- `src/vibe3/orchestra/result_handler.py` — 改为 shim
- `src/vibe3/orchestra/command_builder.py` — 改为 shim
- `src/vibe3/orchestra/prompts.py` — 改为 shim
- `src/vibe3/orchestra/services/assignee_dispatch.py` — 改 import
- `src/vibe3/orchestra/services/state_label_dispatch.py` — 改 import
- `src/vibe3/orchestra/services/pr_review_dispatch.py` — 改 import

*depends on Phase 1*

---

### Phase 3: 精简 Dispatcher，删除旧 dispatcher.py

**目标**：orchestra/dispatcher.py 退役，被 manager_executor 完全替代

**步骤**：
1. 确认所有 external consumer 已指向 manager：
   - `server/registry.py` 引用 `ManagerExecutor` 替代 `Dispatcher`
   - `orchestra/services/*.py` 引用 `ManagerExecutor`
   - `orchestra/__init__.py` 更新 exports
2. 删除 `orchestra/dispatcher.py`（或改为 shim → `manager/manager_executor.py`）
3. 更新 `server/registry.py` 的装配逻辑：
   - `shared_manager = ManagerExecutor(config, ...)` 替代 `shared_dispatcher = Dispatcher(config, ...)`
4. GovernanceService 的 `run_governance_command()` 改为调用 `dispatcher.executor.run_command` 直接

**验证**：
- `uv run pytest tests/vibe3/ -v`（全量）
- `uv run mypy src/vibe3/`

**文件变更**：
- `src/vibe3/orchestra/dispatcher.py` — 删除或改为 shim
- `src/vibe3/orchestra/__init__.py` — 更新 exports
- `src/vibe3/server/registry.py` — 改引用
- `src/vibe3/orchestra/services/governance_service.py` — 改：直接用 dispatcher.executor

*depends on Phase 2*

---

### Phase 4: 测试迁移 + Shim 清理

**目标**：测试文件与代码结构对齐，删除过渡 shim

**步骤**：
1. 创建 `tests/vibe3/manager/` 目录
2. 迁移相关测试：
   - `test_dispatcher.py` → `tests/vibe3/manager/test_manager_executor.py`
   - `test_dispatcher_manager.py` → `tests/vibe3/manager/test_dispatch_flow.py`
   - `test_dispatcher_worktree.py` → `tests/vibe3/manager/test_worktree_manager.py`
   - `test_dispatcher_feedback.py` → `tests/vibe3/manager/test_result_handler.py`
3. 创建 `tests/vibe3/dispatcher/` 目录
4. 迁移：
   - `test_circuit_breaker.py` → `tests/vibe3/dispatcher/`
   - `test_dispatcher_error_category.py` → `tests/vibe3/dispatcher/`
5. 删除 orchestra/ 下所有 shim 文件
6. 更新 `orchestra/__init__.py` 只导出 orchestra 自有内容

**验证**：
- `uv run pytest tests/vibe3/ -v`
- `uv run mypy src/vibe3/`
- shim 中 `import` 路径无任何残留

*depends on Phase 3*

---

## Relevant Files

**被移动的文件（从 orchestra/ 出发）**：
- `src/vibe3/orchestra/executor.py` — 移到 `dispatcher/`，参考 `run_command()` 函数
- `src/vibe3/orchestra/circuit_breaker.py` — 移到 `dispatcher/`，参考 `CircuitBreaker` 类 + `classify_failure()`
- `src/vibe3/orchestra/flow_orchestrator.py` — 移到 `manager/`，参考 `FlowOrchestrator` 类
- `src/vibe3/orchestra/dispatcher_worktree.py` — 移到 `manager/`，参考 `WorktreeResolverMixin` 类
- `src/vibe3/orchestra/result_handler.py` — 移到 `manager/`，参考 `DispatchResultHandler` 类
- `src/vibe3/orchestra/command_builder.py` — 移到 `manager/`，参考 `CommandBuilder` 类
- `src/vibe3/orchestra/prompts.py` — 移到 `manager/`，参考 `render_manager_prompt()`
- `src/vibe3/orchestra/dispatcher.py` — Phase 3 退役，被 `manager/manager_executor.py` 替代

**需要更改 import 的文件**：
- `src/vibe3/server/registry.py` — 接入新模块路径（核心变更点）
- `src/vibe3/orchestra/services/assignee_dispatch.py` — Dispatcher → ManagerExecutor
- `src/vibe3/orchestra/services/state_label_dispatch.py` — Dispatcher → ManagerExecutor
- `src/vibe3/orchestra/services/pr_review_dispatch.py` — Dispatcher → ManagerExecutor
- `src/vibe3/orchestra/services/governance_service.py` — Dispatcher → dispatcher.executor
- `src/vibe3/orchestra/services/status_service.py` — FlowOrchestrator → FlowManager
- `src/vibe3/orchestra/__init__.py` — 更新 exports

**Worktree 回收新增逻辑**（Phase 2 关键）：
- `src/vibe3/manager/worktree_manager.py` — 新增 `recycle()`, `_should_recycle()`
- `src/vibe3/manager/manager_executor.py` — finally 中调用 worktree 回收

---

## Verification

1. **Phase 1 验证**：`uv run pytest tests/vibe3/orchestra/test_circuit_breaker.py tests/vibe3/orchestra/test_dispatcher_error_category.py -v` + `uv run mypy src/vibe3/dispatcher/`
2. **Phase 2 验证**：`uv run pytest tests/vibe3/orchestra/ -v`（全部 orchestra 测试通过 shim 兼容） + `uv run mypy src/vibe3/manager/`
3. **Phase 3 验证**：`uv run pytest tests/vibe3/ -v`（全量） + `uv run mypy src/vibe3/`
4. **Phase 4 验证**：`uv run pytest tests/vibe3/ -v` + 确认 `grep -r "from vibe3.orchestra.executor" src/` 无结果（shim 已删）
5. **全流程验证**：`vibe3 serve start --dry-run` 正常启动，`vibe3 task status` 正常显示

---

## Decisions

- **config.py 不搬**：三层共用配置放在 orchestra/ 是合理的，因为 orchestra 是"编排中心"的语义根
- **master.py / master_handler.py 不搬**：triage 是 orchestra 的职责（决策），不是 manager 的
- **heartbeat / event_bus 不搬**：事件循环归属 orchestra 合理
- **shim 过渡策略**：每个 phase 留 shim 保向后兼容，Phase 4 统一清理
- **FlowOrchestrator 重命名为 FlowManager**：更贴切新模块语义
- **WorktreeResolverMixin 改为独立类 WorktreeManager**：不再是 mixin，有独立生命周期（含回收）
- **排除范围**：不动 V2 shell、不动 skills/、不改 config schema

## Further Considerations

1. **Registry 装配变动幅度**：`server/registry.py` 的 `_build_server()` 需要把 `Dispatcher` 替换为 `ManagerExecutor`。共享实例模式不变（shared_manager 替代 shared_dispatcher），但构造函数参数会变。建议 Phase 2 完成后立即更新 registry 并测试 `vibe3 serve start --dry-run`。

2. **GovernanceService 的 dispatcher 依赖**：Governance 目前用 `Dispatcher.run_governance_command()` 执行 subprocess，它只需要 circuit breaker + subprocess 能力。Phase 3 后改为直接调用 `dispatcher.executor.run_command()`，通过参数注入 circuit breaker 实例。
    