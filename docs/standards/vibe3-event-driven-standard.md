# Vibe3 Event-Driven Architecture Standard

> **文档定位**: 定义 vibe3 事件驱动架构的设计原则、执行链路、事件定义与处理器规范。
> **适用范围**: 所有涉及领域事件发布、订阅、处理的代码路径。
> **权威性**: 本文件是事件驱动架构的唯一权威来源。实现细节以代码为准，架构意图以本文件为准。

---

## 一、核心原则

### 1.1 事件驱动架构价值

**解耦**: Usecase 层与 Service 层通过事件解耦，业务状态变迁不直接依赖具体服务实现。

**可测试**: 事件是不可变的数据结构，易于断言和 mock，支持纯函数式测试。

**可扩展**: 新增业务逻辑只需订阅现有事件，无需修改发布者代码。

**可审计**: 所有业务状态变迁通过事件记录，易于追踪、重放和分析。

### 1.2 事件设计原则

**不可变性**: 所有事件必须是 `frozen=True` 的 dataclass，创建后不可修改。

**单一职责**: 每个事件表示一个独立的业务状态变迁，不承载多余信息。

**显式类型**: 事件类型通过类名明确标识，不依赖字符串匹配（仅用于注册表）。

**命名规范**: 事件名称使用过去式（如 `IssueStateChanged`, `PlanCompleted`）。

**Dispatch Intent 事件命名**（特殊规则）：
- Dispatch Intent 事件使用未来式 + Intent 后缀（如 `ManagerDispatchIntent`）
- 明确表达这是"意图"而非"完成"，避免语义混淆
- 示例：`ManagerDispatchIntent` 表示"应该 dispatch manager"，不是"已 dispatched"
- 向后兼容：旧事件名 `*Dispatched` 作为别名保留

**Audit 事件命名**：
- `audit_recorded` 表示系统解析并记录 audit_ref 的行为
- 区别于 `handoff_*` 事件：handoff 是 agent 主动提交，audit_recorded 是系统被动解析

### 1.3 处理器设计原则

**纯函数**: 处理器应是纯函数或无状态方法，不依赖外部可变状态。

**错误隔离**: 处理器异常不应影响其他处理器执行，由 Publisher 捕获并记录。

**幂等性**: 处理器应支持重复执行而不产生副作用（如使用 `confirm_issue_state` 而非直接 `transition`）。

**单一职责**: 每个处理器只做一件事，复杂逻辑应拆分为多个处理器订阅同一事件。

---

## 二、执行链路定义

```
L0  Orchestra / Heartbeat          -- 调度主循环
L1  Governance Service             -- 定期扫描，只操作 GitHub labels
L2  Supervisor + Apply             -- 轻量治理执行，临时 worktree 隔离
L3  Manager / Plan / Run / Review  -- 代码开发核心，独立 worktree
L4  Human collaboration            -- 人工协作流程
```

**参考**: [vibe3-worktree-ownership-standard.md](vibe3-worktree-ownership-standard.md) §二

---

## 三、四条事件链路

### 3.1 L1 — Governance Chain

**职责**: 定期治理扫描与人工决策触发。

**事件定义** (`src/vibe3/domain/events/governance.py`):

| 事件 | 触发时机 | 关键字段 |
|------|---------|---------|
| `GovernanceScanStarted` | Tick 扫描开始 | `tick_count` |
| `GovernanceScanCompleted` | Tick 扫描完成 | `tick_count`, `active_flows`, `suggested_issues` |
| `GovernanceDecisionRequired` | 需要人工决策 | `issue_number`, `reason`, `suggested_action` |
| `SupervisorExecutionCompleted` | Supervisor 模式执行完成 | `supervisor_file`, `issue_number`, `success` |

**处理器** (`src/vibe3/domain/handlers/governance.py`):
- 记录扫描生命周期日志
- 为需要决策的 issue 添加评论
- 记录 supervisor 执行结果

**集成点**:
- `orchestra/services/governance_service.py` → 发布扫描事件
- `orchestra/supervisor_run_service.py` → 发布执行完成事件

**Worktree 语义**: 通常在主仓库执行，无需独立隔离（`cwd=None`）。

---

### 3.2 L2 — Supervisor Apply Chain

**职责**: 轻量治理执行，可委托复杂任务到 L3。

**事件定义** (`src/vibe3/domain/events/supervisor_apply.py`):

| 事件 | 触发时机 | 关键字段 | 说明 |
|------|---------|---------|------|
| `SupervisorIssueIdentified` | 发现治理 issue | `issue_number`, `supervisor_file` | 带 `supervisor+state/handoff` 标签 |
| `SupervisorPromptRendered` | Prompt 渲染完成 | `prompt_length` | 日志记录用 |
| `SupervisorApplyDispatched` | Apply agent 分发 | `tmux_session` | 异步执行开始 |
| `SupervisorApplyStarted` | Apply 执行开始 | `worktree_path` | 在隔离 worktree 中 |
| `SupervisorApplyCompleted` | Apply 执行完成 | `outcome`, `actions_taken` | 结果记录 |
| `SupervisorApplyDelegated` | 委托到 L3 | `governance_issue_number`, `new_task_issue_number` | 复杂变更降级 |

**处理器** (`src/vibe3/domain/handlers/supervisor_apply.py`):
- 记录 issue 检测与分发状态
- 为 dispatch/queue 添加评论
- 记录委托决策并链接 issue

**集成点**:
- `orchestra/services/supervisor_handoff.py` → 发布所有 L2 事件
- Apply agent hooks → 发布执行开始/完成事件

**Worktree 语义**: 临时隔离 worktree，由系统自动解析并锁定路径（`cwd=wt_path`）。

**委托流程**:
```
Apply agent executes
  → Detects complex changes needed
  → Creates new task issue with spec
  → publish SupervisorApplyDelegated
  → L3 Manager chain takes over
```

---

### 3.3 L3 — Manager Chain

**职责**: Flow 分发与容量管理。

**事件定义** (`src/vibe3/domain/events/manager.py`):

| 事件 | 触发时机 | 关键字段 |
|------|---------|---------|
| `ManagerExecutionStarted` | Manager 开始处理 issue | `issue_number`, `branch` |
| `ManagerExecutionCompleted` | Manager 完成处理 | `issue_number`, `branch` |
| `ManagerFlowDispatched` | Flow 分发到 tmux | `tmux_session` |
| `ManagerFlowQueued` | Flow 排队等待容量 | `active_flows`, `max_capacity` |

**处理器** (`src/vibe3/domain/handlers/manager.py`):
- 记录事件到 flow history
- 为 dispatch/queue 状态添加评论
- 记录容量管理决策

**集成点**:
- `manager/manager_executor.py` → 发布分发/排队事件
- `manager/manager_run_service.py` → 发布执行开始/完成事件

**Worktree 语义**: 持久 issue-worktree，由系统自动解析并锁定路径（`cwd=wt_path`）。

---

### 3.4 L3 — Flow Lifecycle Chain

**职责**: Agent 执行生命周期（Plan/Run/Review）。

**事件定义** (`src/vibe3/domain/events/flow_lifecycle.py`):

| 事件 | 触发时机 | 关键字段 | 说明 |
|------|---------|---------|------|
| `IssueStateChanged` | Issue 状态转换 | `from_state`, `to_state` | 标签变迁 |
| `IssueFailed` | Agent 执行失败 | `reason` | 失败记录 |
| `IssueBlocked` | Issue 被阻塞 | `reason` | 缺少前置条件 |
| `ManagerDispatchIntent` | Manager 调度意图 | `issue_number`, `branch` | 管理分发意图 |
| `PlannerDispatchIntent` | Planner 调度意图 | `issue_number`, `branch` | 计划分发意图 |
| `ExecutorDispatchIntent` | Executor 调度意图 | `issue_number`, `branch` | 执行分发意图 |
| `ReviewerDispatchIntent` | Reviewer 调度意图 | `issue_number`, `branch` | 审查分发意图 |

**处理器** (`src/vibe3/domain/handlers/`):
- `flow_lifecycle.py` — 记录状态变迁日志（纯观察），不执行业务判断
- `dispatch.py` — 接收 dispatch-intent 事件，enrichment with execution context，调用 role builder
- `issue_state_dispatch.py` — manager 专属 dispatch handler（async dispatch via ExecutionCoordinator）

**集成点**:
- `orchestra/services/state_label_dispatch.py` → 发布 dispatch-intent 事件
- `codeagent_runner.py` → no-op gate (state-unchanged → block)
- `domain/handlers/dispatch.py` → handler 读取 flow_state 和 handoff 文件

**Worktree 语义**: 持久 issue-worktree，由系统自动解析并锁定路径（`cwd=wt_path`）。

---

## 四、事件发布规范

### 4.1 发布时机

**状态变迁**: 业务状态发生变化时立即发布事件（如 issue state 改变）。

**阶段完成**: Agent 执行阶段完成时发布事件（如 `PlanCompleted`）。

**决策需求**: 需要人工或系统决策时发布事件（如 `GovernanceDecisionRequired`）。

**委托降级**: 执行能力不足需要降级时发布事件（如 `SupervisorApplyDelegated`）。

### 4.2 事件构造

**必须字段**:
- 业务标识字段（如 `issue_number`, `branch`）
- 原因字段（失败/阻塞场景）

**可选字段**:
- `actor`（默认值已在 dataclass 中定义）
- `timestamp`（由系统填充，发布者不设置）
- `reason`（状态变迁原因，可选）

**示例**:
```python
from vibe3.domain.events import PlanCompleted
from vibe3.domain.publisher import publish

event = PlanCompleted(
    issue_number=123,
    branch="dev/feature",
    # actor 默认为 "agent:plan"，不需要显式设置
)
publish(event)
```

### 4.3 发布位置

**Usecase 层**: 事件发布应在 Usecase 层（`agents/`, `manager/`, `orchestra/services/`）进行，不在 Service 层或更低层发布。

**回调函数**: Agent 的 `on_success` / `on_failure` 回调中发布事件，不在执行逻辑内部硬编码。

**异常处理**: 异常场景发布 `IssueFailed` 事件，而不是静默失败。

---

## 五、处理器注册规范

### 5.1 注册时机

应用启动时统一注册，由 `register_event_handlers()` 函数协调。

**位置**: `src/vibe3/domain/handlers/__init__.py`

**顺序**: 按层级顺序注册（L1 → L2 → L3），确保底层依赖先注册。

```python
def register_event_handlers() -> None:
    """Register all event handlers with the global publisher.

    Registration order:
    1. L3 Flow Lifecycle handlers
    2. L3 Issue-state role dispatch handlers
    3. L3 Dispatch handlers (planner/executor/reviewer)
    4. L1 Governance scan handler
    5. L2 Supervisor scan handler
    """
    register_flow_lifecycle_handlers()
    register_issue_state_dispatch_handlers()
    register_dispatch_handlers()
    register_governance_scan_handlers()
    register_supervisor_scan_handlers()
```

### 5.2 注册调用

**CLI 入口**: 在 `src/vibe3/cli.py` 的 `main_callback` 中调用。

```python
@app.callback()
def main_callback(verbose: int = 0) -> None:
    setup_logging(verbose=verbose)

    # Register domain event handlers
    from vibe3.domain.handlers import register_event_handlers
    register_event_handlers()
```

### 5.3 处理器签名

**类型安全**: 处理器必须有完整类型注解，通过 `mypy --strict` 检查。

**参数类型**: 接收具体事件类型，而非基类 `DomainEvent`。

**返回类型**: 返回 `None`，不返回值。

**示例**:
```python
def handle_plan_completed(event: PlanCompleted) -> None:
    """Handle PlanCompleted event."""
    # Validate plan_ref
    # Transition issue state
    # Log completion
```

### 5.4 类型转换

由于 contravariance 规则，注册时需要 `cast` 转换。

```python
from typing import cast
from vibe3.domain.publisher import subscribe

subscribe(
    "PlanCompleted",
    cast(Callable[[DomainEvent], None], handle_plan_completed),
)
```

### 5.5 向后兼容性注册

**事件重命名场景**：当事件名称变更时，必须保持向后兼容。

**注册方式**：同时订阅新旧事件名称。

```python
# 新事件名称
subscribe(
    "ManagerDispatchIntent",
    cast(Callable[[DomainEvent], None], handle_manager_dispatch_intent),
)

# 向后兼容：订阅旧事件名称
subscribe(
    "ManagerDispatched",  # 旧名称
    cast(Callable[[DomainEvent], None], handle_manager_dispatch_intent),
)
```

**事件定义**：在事件类定义中提供别名。

```python
@dataclass(frozen=True)
class ManagerDispatchIntent(DomainEvent):
    """Manager dispatch intent event."""
    ...

# 向后兼容别名
ManagerDispatched = ManagerDispatchIntent
```

**事件注册表**：支持新旧名称映射。

```python
EVENT_TYPES = {
    # 新名称
    "manager_dispatch_intent": ManagerDispatchIntent,
    # 向后兼容
    "manager_dispatched": ManagerDispatchIntent,
}
```

---

## 六、Worktree 语义与事件

**参考**: [vibe3-worktree-ownership-standard.md](vibe3-worktree-ownership-standard.md)

### 6.1 L1 Governance Events

- **Worktree**: 无
- **参数**: `cwd=None`，无 `--worktree`
- **理由**: 只读操作，不修改代码

### 6.2 L2 Supervisor Apply Events

- **Worktree**: 临时隔离（`--worktree` 标志）
- **参数**: `cwd=None`，使用 `--worktree`
- **理由**: 可能修改文档/配置，需要隔离空间
- **事件字段**: `worktree_path`（由 Apply agent 提供）

### 6.3 L3 Manager / Flow Lifecycle Events

- **Worktree**: 预分配（WorktreeManager）
- **参数**: `cwd=wt_path`，禁止 `--worktree`
- **理由**: 完整开发流程，需要持久化环境
- **事件字段**: `branch`（WorktreeManager 根据 branch 分配）

### 6.4 Worktree 字段规范

| 链路 | 事件字段 | 来源 | 语义 |
|------|---------|------|------|
| L1 | 无 | - | 不需要 worktree |
| L2 | `worktree_path` | Agent 运行时 | 临时创建的隔离路径 |
| L3 | `branch` | Flow 绑定 | 预分配的持久化路径 |

---

## 七、文件组织规范

### 7.1 目录结构

```
src/vibe3/domain/
├── __init__.py                    # 主导出
├── publisher.py                   # EventPublisher (singleton)
├── events/
│   ├── __init__.py               # 重导出所有事件 + 事件注册表
│   ├── governance.py             # L1 事件定义
│   ├── supervisor_apply.py       # L2 事件定义
│   ├── manager.py                # L3 Manager 事件定义
│   └── flow_lifecycle.py         # L3 Flow Lifecycle 事件定义
└── handlers/
    ├── __init__.py               # 注册编排
    ├── governance.py             # L1 处理器
    ├── supervisor_apply.py       # L2 处理器
    ├── manager.py                # L3 Manager 处理器
    └── flow_lifecycle.py         # L3 Flow Lifecycle 处理器
```

### 7.2 文件职责

**`events/__init__.py`**:
- 导入子模块事件类
- 重导出统一接口
- 维护 `EVENT_TYPES` 注册表（用于动态查找）

**`handlers/__init__.py`**:
- 导入子模块注册函数
- 提供 `register_event_handlers()` 统一入口
- 不定义具体处理器逻辑

**子模块文件**:
- 每个链路独立文件
- 事件定义与处理器分离（events/ vs handlers/）
- 不跨链路引用

---

## 八、测试规范

### 8.1 单元测试

**位置**: `tests/vibe3/domain/test_events.py`

**覆盖内容**:
- 事件创建（所有字段）
- 事件不可变性（`frozen=True`）
- Publisher 单例模式
- Subscribe/Publish 机制

**示例**:
```python
def test_plan_completed_event():
    event = PlanCompleted(
        issue_number=100,
        branch="dev/feature",
    )
    assert event.issue_number == 100
    assert event.branch == "dev/feature"
    assert event.actor == "agent:plan"
```

### 8.2 集成测试

**位置**: `tests/vibe3/integration/test_event_flow.py`

**覆盖内容**:
- 事件发布到处理器调用的完整链路
- 处理器副作用（如 GitHub API 调用）
- 多个处理器订阅同一事件

### 8.3 类型检查

**命令**: `uv run mypy src/vibe3/domain --strict`

**要求**: 所有事件和处理器代码必须通过严格类型检查。

---

## 九、错误处理

### 9.1 处理器异常

**Publisher 行为**:
- 捕获处理器异常，记录日志
- 继续执行其他处理器，不中断
- 异常信息包含事件类型和处理器名称

**日志格式**:
```
ERROR | vibe3.domain.publisher | Handler failed for PlanCompleted: <exception message>
```

### 9.2 防御性检查

**前置验证**: 处理器应验证事件字段合法性。

```python
def handle_plan_completed(event: PlanCompleted) -> None:
    if not event.issue_number:
        logger.warning("PlanCompleted event missing issue_number")
        return

    # Continue with valid event
```

### 9.3 幂等性保障

**重复执行**: 处理器应能安全重复执行。

**示例**:
```python
# ✅ 正确：幂等操作
LabelService().confirm_issue_state(
    issue_number,
    to_state=IssueState.HANDOFF,
    actor=event.actor,
)

# ❌ 错误：非幂等操作
LabelService().transition(
    issue_number,
    to_state=IssueState.HANDOFF,
    force=False,  # 第二次执行会失败
)
```

---

## 十、性能与监控

### 10.1 性能考虑

**同步执行**: 当前所有处理器同步执行，阻塞发布者。

**未来优化**:
- 引入异步处理器支持（`async def handler(event)`）
- 使用消息队列解耦（如 Redis Streams）
- 处理器并行执行

### 10.2 监控指标

**建议指标**:
- 事件发布频率（按类型分组）
- 处理器执行时长（P50, P95, P99）
- 处理器失败率
- 注册处理器数量

**日志级别**:
- `INFO`: 正常事件发布和处理
- `WARNING`: 无处理器订阅、业务阻塞
- `ERROR`: 处理器异常

---

## 十一、与其他标准的关系

### 11.1 引用标准

- **[vibe3-worktree-ownership-standard.md](vibe3-worktree-ownership-standard.md)**: 定义执行层级与 worktree 语义，本文件补充事件语义。
- **[vibe3-orchestra-runtime-standard.md](vibe3-orchestra-runtime-standard.md)**: 定义 driver/tick/async child 架构，事件发布时机参考该文件。
- **[vibe3-state-sync-standard.md](vibe3-state-sync-standard.md)**: 定义 flow 状态机，事件触发条件参考该文件。
- **[agent-debugging-standard.md](agent-debugging-standard.md)**: 调试手册，事件日志规范以本文件为准。

### 11.2 术语真源

- **执行层级（L0-L4）**: 以 `vibe3-worktree-ownership-standard.md` 为准
- **事件类型与语义**: 以本文件为准
- **Worktree 参数规则**: 以 `vibe3-worktree-ownership-standard.md` 为准
- **事件处理器行为**: 以本文件为准

---

## 十二、三层概念说明：governance / apply / runtime

以下三个概念容易混淆，特此明确：

**governance scan**（L1）
- 周期扫描观察，`WorktreeRequirement.NONE`，无 worktree
- 事件链：`GovernanceScanRequested` → `GovernanceScanCompleted` / `SupervisorExecutionCompleted`
- 材料来源：`supervisor/governance/*.md`
- `assignee-pool governance`：观察当前 assignee issue pool
- `roadmap governance`：扫描 broader repo issue pool，把适合自动化推进的 bug fix / small feature 纳入 assignee issue pool；不处理 discussion / refactor / big feature
- `cron governance`：周期性派发过时文档治理 supervisor issue；当前固定一批最多 5 个文档
- governance 不进入主代码实现链；动作限于观察、最小 routing、派单

**supervisor/apply**（L2）
- 执行治理动作，`WorktreeRequirement.TEMPORARY`，有临时 worktree
- 事件链：`SupervisorIssueIdentified` → `SupervisorApplyDispatched` / `SupervisorApplyDelegated`
- 材料来源：`supervisor/apply.md`
- **只处理 supervisor issue（带 `supervisor` label），不处理 assignee issue**
- 执行 label/comment/close/recreate 等动作
- 可在 L2 临时分支完成文档类与测试修补类修改，并直接 commit / push / pr create

**runtime**
- 指 vibe3 服务器运行时（EventBus、Heartbeat、HTTP server）
- 与上述两个治理概念无关，负责基础事件调度与 tick 循环

这三个概念不等价，不可混用。见 `vibe3-worktree-ownership-standard.md` §二 了解完整层级定义。

### Issue 池边界总结

| 角色 | 处理对象 | 说明 |
|------|---------|------|
| governance scan | assignee issue pool | `supervisor/governance/assignee-pool.md` |
| governance/roadmap | broader repo issue pool | 自动纳入适合自动化推进的 bug fix / small feature 到 assignee issue pool |
| governance/cron | broader repo docs scope | 每轮最多派发 5 个过时文档到 supervisor issue |
| supervisor/apply | supervisor issue | 显式立项的治理 issue，带 `supervisor` label |
| manager | assignee issue | 已进入执行池的 issue，由 manager 主链推进 |

---

## 十三、变更历史

| 版本 | 日期 | 变更说明 |
|------|------|----------|
| 1.2 | 2026-04-21 | 补充 governance/apply/runtime 三层概念说明，消除混淆 |
| 1.1 | 2026-04-21 | 重命名 Dispatch 事件为 *DispatchIntent，明确语义；添加 audit_recorded 事件；补充向后兼容性注册规范 |
| 1.0 | 2026-04-08 | 初始版本，定义四条执行链路的事件驱动架构 |

---

**维护者**: Vibe Team
**最后更新**: 2026-04-21
