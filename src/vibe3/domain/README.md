# Domain

事件驱动架构的核心，定义领域事件与处理器。

## 职责

- 事件定义：定义系统中所有领域事件（flow 生命周期、治理决策、supervisor 扫描）
- 事件发布：提供事件发布机制，将事件分发给注册的处理器
- 状态机规则：定义 issue 状态转变规则与事件触发逻辑
- 事件处理器注册：协调多层执行链的事件分发

## 文件列表

统计时间：2026-07-01（当前 worktree 快照）

### 顶层文件

| 文件 | 行数 | 职责 |
|------|------|------|
| `__init__.py` | 207 | 公开 API 导出 |
| `dispatch_coordinator.py` | ~400 | 全局分发协调器（容量感知的意图分发） |
| `dispatch_health.py` | ~150 | 分发健康检查 |
| `dispatch_preflight.py` | ~200 | 分发前置检查 |
| `dispatch_queue_collection.py` | ~300 | 分发队列收集 |
| `dispatch_queue_maintenance.py` | ~200 | 分发队列维护 |
| `event_rules.py` | ~180 | 事件规则引擎（声明式规则 → handler 映射） |
| `failed_gate.py` | ~80 | 失败门控 |
| `flow_manager.py` | ~350 | Flow 生命周期状态机入口 |
| `handler_registry.py` | ~120 | 处理器注册表 |
| `orchestration_facade.py` | ~350 | 编排门面（runtime tick/heartbeat → 发布 events） |
| `publisher.py` | ~90 | 事件发布器（全局单例） |
| `qualify_gate.py` | ~250 | 资格门控（issue 准入校验） |
| `qualify_gate_checks.py` | ~180 | 资格门控检查实现 |
| `qualify_gate_support.py` | ~120 | 资格门控辅助函数 |
| `role_resolver.py` | ~100 | IssueState → TriggerName 解析 |

### events/ 子目录

| 文件 | 行数 | 职责 |
|------|------|------|
| `__init__.py` | ~150 | 事件类型导出 |
| `base.py` | ~50 | DomainEvent 基类定义 |
| `flow_lifecycle.py` | ~180 | Flow 生命周期事件定义 |
| `governance.py` | ~70 | 治理决策事件定义 |
| `policy.py` | ~40 | 策略变更事件定义 |
| `supervisor_apply.py` | ~150 | Supervisor 扫描结果应用事件定义 |

### handlers/ 子目录

| 文件 | 行数 | 职责 |
|------|------|------|
| `__init__.py` | ~60 | 处理器导出与注册函数 |
| `dispatch.py` | ~300 | 分发事件处理器（协调三层执行链） |
| `flow_lifecycle.py` | ~100 | Flow 生命周期事件处理器 |
| `governance_scan.py` | ~160 | 治理扫描处理器（L1 层） |
| `issue_state_dispatch.py` | ~200 | Issue 状态转变分发处理器 |
| `manual_dispatch.py` | ~180 | 手动触发分发处理器 |
| `supervisor_scan.py` | ~110 | Supervisor 扫描处理器（L2 层） |

### protocols/ 子目录

| 文件 | 行数 | 职责 |
|------|------|------|
| `__init__.py` | ~40 | 协议导出 |
| `dispatch_protocols.py` | ~80 | 分发相关协议定义 |
| `flow_protocols.py` | ~60 | Flow 相关协议定义 |
| `infra_protocols.py` | ~50 | 基础设施协议定义 |
| `orchestra_protocols.py` | ~70 | 编排协议定义 |
| `runtime_protocols.py` | ~60 | 运行时协议定义 |

**总计**：35 文件，约 6294 行

## 公开 APIs

核心入口（均以 `vibe3.domain.X` lazy import 公开，引用 `src/vibe3/domain/__init__.py`）：

| 入口 | 角色 | 主要消费者 |
|------|------|----------|
| `OrchestrationFacade` | 观察入口：runtime tick / heartbeat → 发布 domain events + 编排 dispatch coordinator | `src/vibe3/server/registry.py`（composition-root 实例），`domain/orchestration_facade.py` 内部自引用 |
| `GlobalDispatchCoordinator` | 容量感知的意图分发（L1/L2/L3 并发协调，上限 `MAX_INTENTS_PER_TICK`） | `OrchestrationFacade._coordinator`（间接实例化） |
| `FlowManager` | Flow 生命周期状态机入口（依赖 services.flow / services.pr / services.issue / services.orchestra） | `src/vibe3/services/flow/factory.py`（lazy 透传给 roles），`domain/orchestration_facade.py` |
| `publish / publish_and_wait / subscribe / EventPublisher` | 事件总线（全局单例 via `get_publisher()`） | `handlers/*.py` 订阅；`commands/scan.py` 等触发 |
| `register_event_handlers` | 一次性注册 `@register_handler` 带装饰器的 handlers（避免循环依赖） | `commands/{plan,run,review,task,scan}.py` 入口 |
| `QualifyGateService` | 资格门控（issue 准入校验，依赖 services.flow/issue/shared/task） | `dispatch_coordinator.py`、`dispatch_queue_collection.py` |
| `FailedGate` | 失败门控（依赖 services.orchestra.ErrorTrackingService） | `dispatch_coordinator.py` |
| `find_role_for_state` | IssueState → TriggerName 解析 | `domain/handlers/issue_state_dispatch.py`、`domain/handlers/manual_dispatch.py` |
| `EventRule / load_rules / evaluate_rules / build_action_handlers` | 事件规则引擎（声明式规则 → handler 映射） | `event_rules.py` 内部，`handlers/dispatch.py` |

事件类型（`vibe3.domain.events.*`，均为 `DomainEvent` 子类，frozen dataclass）：

- **L3 Flow Lifecycle**: `FlowBlocked / FlowCompleted / PRMerged / IssueFailed / ManagerDispatchIntent / PlannerDispatchIntent / ExecutorDispatchIntent / ReviewerDispatchIntent / Manual{Plan,Run,Review}Intent / ControlPlaneEventPublished`
- **L1 Governance**: `GovernanceScanStarted / GovernanceScanCompleted / GovernanceDecisionRequired`
- **L2 Supervisor Apply**: `SupervisorIssueIdentified / SupervisorPromptRendered / SupervisorApply{Dispatched,Started,Completed,Delegated}`
- **Policy**: `PolicyChanged`

## 三层协作关系

```
domain (事件源)
  └─ OrchestrationFacade.on_tick() 发布 events
       ├─ GovernanceScanStarted → governance_scan handler
       │    └─ execution.run_governance_sync → roles.build_default_governance_fns
       ├─ SupervisorIssueIdentified → supervisor_scan handler
       │    └─ execution.run_issue_role_* → roles.SUPERVISOR_CLI_SYNC_SPEC
       └─ *DispatchIntent / Manual*Intent → dispatch / manual_dispatch handler
            └─ ExecutionCoordinator.dispatch_execution(request)
                 └─ CodeagentExecutionService.execute_sync(command)
                      └─ 角色具体逻辑（roles/{manager,plan,run,review,supervisor,governance}.py）
```

> 关键约束：roles 不直接 import domain（避免循环依赖）；roles 通过 `vibe3.execution` 公开 API 调用执行层，二者构成强组合关系。roles 通过 `services/flow/factory.py`（`create_flow_manager`）与 `services/shared/events.py`（`emit_issue_failed`）间接消费 domain 事件。

## services 层依赖

domain 模块主要依赖 `services.{flow,pr,issue,orchestra,shared,task}`：
- `FlowManager` 直接依赖 `services.flow.FlowService` 和 `services.pr.PRService` 管理 flow 生命周期
- `QualifyGateService` 依赖 `services.flow`、`services.issue`、`services.task` 执行准入检查
- `FailedGate` 依赖 `services.orchestra.ErrorTrackingService` 记录失败
- 执行结果通过 `services.shared.events` 发布 `IssueFailed` 事件

注：services 层不反向依赖 domain（services 是 L3 基础层）。

## 依赖关系

### 依赖

- `config`：编排配置加载
- `models`：领域模型定义
- `exceptions`：领域异常
- `clients`：GitHub 客户端（事件通知）
- `services`：状态标签分发服务
- `execution`：容量服务、执行协调

### 被依赖

- `execution`：事件触发执行
- `roles`：角色监听事件
- `orchestra`：全局编排协调
- `commands`：命令层触发事件

## 架构说明

### 三层执行链

Domain 模块实现了三层执行链架构，通过事件驱动协调不同层级的执行：

- **L1 治理层（Governance）**：定期扫描，发现系统级问题并触发修复建议
- **L2 监管层（Supervisor）**：扫描执行状态，处理异常情况并触发恢复
- **L3 代理层（Agent）**：执行具体任务，响应 issue 状态变化

### 关键组件

1. **OrchestrationFacade**：观察入口，将 runtime tick 转换为 domain events
2. **GlobalDispatchCoordinator**：容量感知的分发协调，控制 L1/L2/L3 并发上限
3. **QualifyGateService**：资格门控，校验 issue 是否满足执行条件
4. **FailedGate**：失败门控，记录失败并触发错误处理
5. **EventRule Engine**：声明式规则引擎，将事件映射到处理器

### 事件流

```
Issue State Change → Event Publisher → Handlers
                                        ├─ Governance Handler (L1)
                                        ├─ Supervisor Handler (L2)
                                        └─ Agent Dispatch (L3)
```

### 关键设计

1. **事件解耦**：各层通过事件通信，避免直接依赖
2. **优先级队列**：L1 > L2 > L3 的执行优先级
3. **状态机驱动**：issue 状态转变自动触发相应事件
4. **容量控制**：通过 capacity service 控制并发执行数
5. **双重门控**：QualifyGate（准入）+ FailedGate（失败处理）

## 与 main 分支差异

当前 worktree 相对 origin/main 落后约 11 个 commits（涉及 domain/execution/roles），主要差异：

1. **新增 `dispatch_lifecycle.py`**：main 分支已加入 `DispatchLifecycle` FSM（状态机），管理 dispatch 生命周期。当前 worktree 尚未 rebase，`domain/__init__.py` 中无此导出。
   - 新增符号：`DispatchLifecycle`、`DispatchLifecycleConfig`、`DispatchState`
   - 建议：rebase 到 origin/main 后更新 README

2. **历史文件清理**：`domain/state_machine.py` 已在更早提交中移除；当前 worktree 与 main 均不再包含该文件。
