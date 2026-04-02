# Plan v5: 四层模块重构 — server / runtime / orchestra / manager

## TL;DR

将当前 `server/` + `orchestra/` + `manager/` + `dispatcher/` 整理为四层模块：
- **server** — HTTP/webhook 入口（已完成）
- **runtime** — 事件循环 + 执行引擎 + 故障保护（新建，合并 dispatcher/ + heartbeat + event_bus）
- **orchestra** — 状态机 + 治理 + 触发服务（精简）
- **manager** — 执行现场管理（已完成，需增加 queue）

**关键约束**：dispatcher/ 不作为独立模块存在，并入 runtime。

---

## 当前现状（已执行的变更）

| 模块          | 状态     | 内容                                                                                                                                                                           |
| ------------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `server/`     | 已完成   | `app.py`, `mcp.py`, `registry.py`                                                                                                                                              |
| `dispatcher/` | 已创建   | `executor.py`, `circuit_breaker.py`（应并入 runtime）                                                                                                                          |
| `manager/`    | 已创建   | `manager_executor.py`, `flow_manager.py`, `worktree_manager.py`, `command_builder.py`, `result_handler.py`, `prompts.py`                                                       |
| `orchestra/`  | 部分精简 | 仍含 `heartbeat.py`, `event_bus.py`（应移入 runtime）；含旧 shim（`serve.py`, `serve_utils.py`, `mcp_server.py`, `webhook_handler.py`, `dispatcher.py`, `circuit_breaker.py`） |

### 现有 shim 清单（待清理）

- `orchestra/serve.py` → shim → `server/app`
- `orchestra/serve_utils.py` → shim → `server/registry`
- `orchestra/mcp_server.py` → shim → `server/mcp`
- `orchestra/webhook_handler.py` → shim → `server/app`
- `orchestra/dispatcher.py` → shim → `manager/manager_executor`（class Dispatcher 继承 ManagerExecutor）
- `orchestra/circuit_breaker.py` → shim → `dispatcher/circuit_breaker`

### 测试现状

全部 23 个 orchestra 测试仍在 `tests/vibe3/orchestra/`，无 `tests/vibe3/manager/` 或 `tests/vibe3/dispatcher/`。

---

## 目标四层架构

```
server/          ← HTTP 入口（已完成）
  app.py           FastAPI + webhook router
  mcp.py           MCP server
  registry.py      装配 heartbeat + services + FastAPI

runtime/         ← 事件循环 + 执行引擎（NEW: 合并 dispatcher/ + heartbeat + event_bus）
  heartbeat.py     HeartbeatServer（来自 orchestra/heartbeat.py）
  event_bus.py     GitHubEvent + ServiceBase（来自 orchestra/event_bus.py）
  executor.py      run_command()（来自 dispatcher/executor.py）
  circuit_breaker.py  CircuitBreaker（来自 dispatcher/circuit_breaker.py）

orchestra/       ← 状态机 + 治理（精简）
  config.py        全局配置（不动）
  master.py        triage AI agent（不动）
  master_handler.py（不动）
  dependency_checker.py（不动）
  services/
    assignee_dispatch.py    唯一触发源（不动）
    governance_service.py   AI 治理扫描（不动）
    comment_reply.py        评论应答（不动）
    pr_review_dispatch.py   PR review 触发（不动）
    status_service.py       只读聚合（需升级：running/queued/blocked）
    state_label_dispatch.py 保留但降级为 mirror-only（不触发 dispatch）

manager/         ← 执行现场管理（已完成，需增加 queue）
  manager_executor.py  统一编排入口（需改：can_dispatch → start_or_queue）
  flow_manager.py      flow 生命周期
  worktree_manager.py  worktree 生命周期
  command_builder.py   命令构造
  result_handler.py    结果处理
  prompts.py           prompt 模板
```

---

## 分步实施

### Phase 1: 创建 runtime/ 模块（合并 dispatcher + heartbeat + event_bus）

**目标**：把事件循环和执行引擎统一到 runtime/

**步骤**：
1. 创建 `src/vibe3/runtime/__init__.py`
2. 移动文件：
   - `dispatcher/executor.py` → `runtime/executor.py`
   - `dispatcher/circuit_breaker.py` → `runtime/circuit_breaker.py`
   - `orchestra/heartbeat.py` → `runtime/heartbeat.py`
   - `orchestra/event_bus.py` → `runtime/event_bus.py`
3. 原位留 shim（保向后兼容）：
   - `dispatcher/executor.py` → `from vibe3.runtime.executor import ...`
   - `dispatcher/circuit_breaker.py` → `from vibe3.runtime.circuit_breaker import ...`
   - `orchestra/heartbeat.py` → `from vibe3.runtime.heartbeat import ...`
   - `orchestra/event_bus.py` → `from vibe3.runtime.event_bus import ...`
4. 更新直接 import 的消费者（渐进式，可选）：
   - `manager/manager_executor.py`：`from vibe3.dispatcher.*` → `from vibe3.runtime.*`
   - `orchestra/services/governance_service.py`：同上
   - `orchestra/services/status_service.py`：同上
   - `server/registry.py`：`from vibe3.orchestra.heartbeat` → `from vibe3.runtime.heartbeat`

**验证**：
```bash
uv run pytest tests/vibe3/orchestra/test_heartbeat.py tests/vibe3/orchestra/test_circuit_breaker.py tests/vibe3/orchestra/test_dispatcher_error_category.py -v
uv run mypy src/vibe3/runtime/
```

**文件变更**：
- `src/vibe3/runtime/__init__.py` — 新建
- `src/vibe3/runtime/executor.py` — 来自 dispatcher/executor.py
- `src/vibe3/runtime/circuit_breaker.py` — 来自 dispatcher/circuit_breaker.py
- `src/vibe3/runtime/heartbeat.py` — 来自 orchestra/heartbeat.py
- `src/vibe3/runtime/event_bus.py` — 来自 orchestra/event_bus.py
- `src/vibe3/dispatcher/executor.py` — 改为 shim
- `src/vibe3/dispatcher/circuit_breaker.py` — 改为 shim
- `src/vibe3/orchestra/heartbeat.py` — 改为 shim
- `src/vibe3/orchestra/event_bus.py` — 改为 shim

**无依赖，第一步**

---

### Phase 2: 完善 import 迁移 + 删除 dispatcher/

**目标**：所有消费者直接引用 runtime/，删除 dispatcher/ 目录

**步骤**：
1. 全局替换 `from vibe3.dispatcher.` → `from vibe3.runtime.`：
   - `src/vibe3/manager/manager_executor.py`（2 处）
   - `src/vibe3/orchestra/services/governance_service.py`（1 处）
   - `src/vibe3/orchestra/services/status_service.py`（1 处 TYPE_CHECKING）
2. 全局替换 `from vibe3.orchestra.heartbeat` → `from vibe3.runtime.heartbeat`：
   - `src/vibe3/server/registry.py`（1 处）
3. 全局替换 `from vibe3.orchestra.event_bus` → `from vibe3.runtime.event_bus`：
   - `src/vibe3/orchestra/services/assignee_dispatch.py`
   - `src/vibe3/orchestra/services/state_label_dispatch.py`
   - `src/vibe3/orchestra/services/pr_review_dispatch.py`
   - `src/vibe3/orchestra/services/comment_reply.py`
   - `src/vibe3/orchestra/services/governance_service.py`
   - `src/vibe3/orchestra/services/status_service.py`（如有）
4. 更新 `runtime/heartbeat.py` 内部 import：
   - `from vibe3.orchestra.config` → 保持不变（config 仍在 orchestra/）
   - `from vibe3.orchestra.event_bus` → `from vibe3.runtime.event_bus`
5. 删除 `src/vibe3/dispatcher/` 目录
6. 更新测试 import（`test_circuit_breaker.py`, `test_dispatcher_error_category.py`）

**验证**：
```bash
uv run pytest tests/vibe3/orchestra/ -v
uv run mypy src/vibe3/runtime/ src/vibe3/manager/ src/vibe3/server/
```

**依赖 Phase 1**

---

### Phase 3: Shim 清理（orchestra 内旧 shim 全删）

**目标**：删除 orchestra/ 中已无消费者的 shim 文件

**待删 shim 文件**：
- `orchestra/serve.py` — shim → server/app
- `orchestra/serve_utils.py` — shim → server/registry
- `orchestra/mcp_server.py` — shim → server/mcp
- `orchestra/webhook_handler.py` — shim → server/app
- `orchestra/dispatcher.py` — shim → manager/manager_executor
- `orchestra/circuit_breaker.py` — shim → runtime/circuit_breaker（旧址是 dispatcher/）

**步骤**：
1. `grep -r` 确认每个 shim 无外部消费者（仅测试文件可能引用）
2. 更新引用 shim 路径的测试文件
3. 删除 shim 文件
4. 更新 `orchestra/__init__.py`

**验证**：
```bash
uv run pytest tests/vibe3/ -v
uv run mypy src/vibe3/
grep -r "from vibe3.orchestra.serve\b" src/ tests/
grep -r "from vibe3.orchestra.dispatcher\b" src/ tests/
grep -r "from vibe3.orchestra.webhook_handler\b" src/ tests/
```

**依赖 Phase 2**

---

### Phase 4: 测试文件重组

**目标**：测试目录与模块结构对齐

**步骤**：
1. 创建 `tests/vibe3/runtime/`
2. 迁移：
   - `test_heartbeat.py` → `tests/vibe3/runtime/`
   - `test_circuit_breaker.py` → `tests/vibe3/runtime/`
   - `test_dispatcher_error_category.py` → `tests/vibe3/runtime/`
3. 创建 `tests/vibe3/manager/`
4. 迁移：
   - `test_dispatcher.py` → `tests/vibe3/manager/test_manager_executor.py`
   - `test_dispatcher_manager.py` → `tests/vibe3/manager/test_dispatch_flow.py`
   - `test_dispatcher_feedback.py` → `tests/vibe3/manager/test_result_handler.py`
   - `test_dispatcher_worktree.py`（如存在）→ `tests/vibe3/manager/test_worktree_manager.py`
5. 更新所有迁移测试的 import 路径

**验证**：
```bash
uv run pytest tests/vibe3/ -v
```

**依赖 Phase 3**

---

## 后续演进（不在本轮实施）

以下是 v4 讨论中确认的架构决策，但属于新 feature，不在本轮模块拆分中实现：

1. **Queue 准入控制**：`can_dispatch()` → `start_or_queue()`，容量满时排队不拒绝
2. **State labels mirror-only**：`state_label_dispatch.py` 不再触发 dispatch，只做状态镜像
3. **Status 面板升级**：`OrchestraSnapshot` 增加 running/queued/blocked 分类
4. **结构化结果反馈**：manager 的 dispatch 返回 `DispatchResult` 而非 `bool`
5. **上层控制接口**：orchestra 可 reorder queue / abort running

> 这些演进基于本轮模块拆分完成后进行，每项可独立 PR。

---

## Decisions

- **config.py 留在 orchestra/**：config 是 "编排策略" 的配置
- **heartbeat + event_bus 移入 runtime/**：它们是运行时引擎，不是编排策略
- **dispatcher/ 不独立存在**：executor 和 circuit_breaker 是运行时基础设施，并入 runtime
- **master.py / dependency_checker.py 留在 orchestra/**：triage 和依赖分析是编排决策
- **shim 策略**：Phase 1-2 留 shim 保向后兼容，Phase 3 统一清理
- **架构制约**：runtime 不依赖 orchestra/services；orchestra/services 通过 manager 间接使用 runtime 能力
- **排除范围**：不动 V2 shell、不动 skills/、不改 config schema、不做 queue 等新 feature

## 依赖关系

```
Phase 1 (创建 runtime/) → Phase 2 (import 迁移 + 删 dispatcher/)
                        → Phase 3 (删旧 shim)
                        → Phase 4 (测试重组)
```

Phase 2、3、4 严格线性依赖。
