# Execution

执行控制平面，协调角色执行与容量控制。

## 职责

- 执行协调：管理角色执行的完整生命周期
- 容量控制：限制并发执行数量，避免资源争抢
- 角色执行请求构建：构建各角色的执行请求和上下文
- No-op 门控：检测并跳过无需执行的任务
- Session 管理：为执行分配独立的 session 和 worktree
- Actor 监督：轻量 worker 抽象与 TTL 清理
- Job 监控：持久化执行状态追踪

## 文件列表

统计时间：2026-07-01（当前 worktree 快照）

### 核心协调文件

| 文件 | 行数 | 职责 |
|------|------|------|
| `__init__.py` | ~140 | 公开 API 导出 |
| `coordinator.py` | ~400 | 执行协调器（容量检查 → worktree/session 分配 → sync/async 分发） |
| `capacity_service.py` | ~120 | 容量服务，控制并发执行数 |
| `contracts.py` | ~50 | 执行契约定义（请求/响应类型） |
| `session_service.py` | ~70 | Session 管理服务 |

### 执行器文件

| 文件 | 行数 | 职责 |
|------|------|------|
| `codeagent_runner.py` | ~420 | Codeagent 执行器（handoff → pre-gate → gate → lifecycle → commit 检测） |
| `codeagent_support.py` | ~90 | Codeagent 辅助函数 |
| `governance_sync_runner.py` | ~120 | Governance 同步执行器 |
| `issue_role_sync_runner.py` | ~200 | Issue 角色同步执行器（plan/run/review） |
| `issue_role_support.py` | ~270 | Issue 角色执行辅助函数 |
| `execution_lifecycle.py` | ~280 | 执行生命周期管理（前缀、后缀处理） |

### 门控与策略文件

| 文件 | 行数 | 职责 |
|------|------|------|
| `noop_gate.py` | ~250 | 统一 no-op 门控（跳过无需执行的任务） |
| `execution_role_policy.py` | ~190 | 执行角色策略（权限控制） |

### 监督与监控文件

| 文件 | 行数 | 职责 |
|------|------|------|
| `actor.py` | ~200 | Actor 监督（轻量 worker 抽象，TTL 清理） |
| `job_executor.py` | ~250 | Job 执行器 |
| `job_monitor_service.py` | ~300 | Job 监控（持久化执行状态） |

### 适配器与元数据文件

| 文件 | 行数 | 职责 |
|------|------|------|
| `command_adapter.py` | ~250 | 命令适配器（vibe-center 等 adapter 资源解析） |
| `prompt_meta.py` | ~90 | Prompt 元数据构建 |
| `role_contracts.py` | ~25 | 角色契约定义 |
| `role_interfaces.py` | ~60 | 角色接口定义 |
| `role_request_factory.py` | ~100 | 角色请求工厂 |
| `auto_scene_recovery.py` | ~80 | 自动场景恢复 |
| `state_verification.py` | ~70 | 状态验证 |

**总计**：23 文件，约 5805 行

## 公开 APIs

核心入口（`vibe3.execution.X` lazy import，引用 `src/vibe3/execution/__init__.py`）：

| 入口 | 角色 | 主要消费者 |
|------|------|----------|
| `ExecutionCoordinator` | 执行请求调度（容量检查 → worktree/session 分配 → sync/async 分发） | `domain/handlers/{governance_scan,supervisor_scan,dispatch,manual_dispatch}.py`，`orchestra/dispatch_coordinator_factory.py` |
| `CodeagentExecutionService` | 同步 codeagent 执行壳（handoff → pre-gate → gate → lifecycle → commit 检测） | `coordinator.py` 内部，`issue_role_sync_runner.py` |
| `run_issue_role_sync / run_issue_role_async` | Issue 角色通用同步/异步 runner（接收 `IssueRoleSyncSpec`） | `commands/internal.py`，`roles/scan_service.py` |
| `run_governance_sync / run_governance_async` | Governance 专用 runner | `commands/scan.py`，`roles/scan_service.py` |
| `apply_unified_noop_gate` | 统一 no-op 门控（跳过无需执行的任务） | `coordinator.py`、`codeagent_runner.py`、`noop_gate.py` 内部 |
| `CapacityService` | 并发容量控制 | `coordinator.py`、`domain/orchestration_facade.py` |
| `ActorRegistry / get_actor_registry / JobActor / ActorStatus / JobType` | Actor 监督（轻量 worker 抽象，TTL 清理） | `server/registry.py`（cleanup hook） |
| `JobMonitorService / JobMonitorSnapshot / ActiveJob` | Job 监控（持久化执行状态） | `job_executor.py`、`job_monitor_service.py` |
| `CommandAdapterRegistry / build_default_registry / ResolvedAdapter` | 命令适配器（vibe-center 等 adapter 资源解析） | `commands/scan.py`、`roles/scan_service.py` |
| `ExecutionRolePolicyService` | 角色执行策略（权限控制） | `execution_role_policy.py` 内部 |
| `PromptMeta / build_prompt_meta` | Prompt 元数据构建 | `coordinator.py`、`codeagent_runner.py` |
| `execution_prefix / persist_execution_lifecycle_event` | 执行生命周期事件持久化 | `codeagent_runner.py`、`coordinator.py` |
| `load_session_id` | Session ID 加载 | `codeagent_runner.py`、`coordinator.py` |
| `GovernanceFunctions` | Governance 角色函数集合 | `roles/governance_factory.py` |
| `build_role_async_request / build_role_sync_request` | 角色请求构建工厂 | `roles/scan_service.py` |

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

execution 模块主要依赖 `services.{flow,orchestra,shared}`：
- `CapacityService` 依赖 `services.flow.FlowService` 查询活跃 flow 数量用于容量计算
- `CodeagentExecutionService` 依赖 `services.orchestra.ErrorTrackingService` 记录执行错误
- 执行结果通过 `services.shared.events` 发布 `IssueFailed` 事件

注：services 层不反向依赖 execution。

## 依赖关系

### 依赖

- `clients`：Git 客户端、SQLite 客户端
- `environment`：Worktree 和 session 管理
- `models`：编排配置、执行请求模型
- `config`：编排配置加载
- `domain`：事件发布、状态机
- `agents`：Agent 后端（Codeagent、异步启动器）

### 被依赖

- `roles`：各角色通过执行器运行
- `domain handlers`：事件处理器触发执行
- `commands`：命令层触发执行

## 架构说明

### Sync vs Async 执行模式

- **同步执行（Sync）**：
  - 阻塞当前线程，等待执行完成
  - 适用于：Governance 扫描、Supervisor 检查、Issue 角色执行
  - 实现：`governance_sync_runner.py`、`issue_role_sync_runner.py`

- **异步执行（Async）**：
  - 启动后台进程，立即返回
  - 适用于：长期运行的任务（如复杂的 plan/run 流程）
  - 实现：`codeagent_runner.py`、异步启动器

### Actor 监督模型

`ActorRegistry` 提供轻量 worker 抽象，支持 TTL 自动清理：

```
ActorRegistry
├─ register(job_type, actor_id) → 注册活跃 actor
├─ cleanup_expired() → 清理超时 actor
└─ get_actor_registry() → 全局单例
```

### Job 监控

`JobMonitorService` 持久化执行状态，支持跨重启恢复：

```
JobMonitorService
├─ record_start(job_id, snapshot) → 记录执行开始
├─ record_completion(job_id, result) → 记录执行完成
└─ get_active_jobs() → 获取活跃执行快照
```

### Command Adapter 机制

`CommandAdapterRegistry` 将不同执行后端适配为统一接口：

```
CommandAdapterRegistry
├─ build_default_registry() → 构建 vibe-center 适配器
├─ resolve(adapter_name) → 解析适配器资源
└─ ResolvedAdapter → 统一执行上下文
```

### Capacity-based Dispatch

容量控制机制避免系统过载：

```
Coordinator
├─ CapacityService.check_capacity() → 是否有空闲槽位
├─ 如果有空位 → 立即执行
└─ 如果无空位 → 排队等待或降级处理
```

### 执行流程

```
1. 接收执行请求
2. No-op 门控检查（是否需要执行）
3. 容量检查（是否有资源执行）
4. Worktree + Session 分配
5. 构建执行上下文（prompt、环境变量）
6. 启动执行（sync/async）
7. 监控执行状态
8. 回收资源（worktree、session）
```

### 关键设计

1. **资源隔离**：每次执行都在独立的 worktree 和 session 中
2. **容量控制**：全局并发限制，避免资源争抢
3. **No-op 优化**：自动跳过无需执行的任务，节省资源
4. **生命周期钩子**：执行前后的初始化和清理逻辑
5. **错误恢复**：执行失败时保留现场，支持恢复
6. **Actor 监督**：轻量 worker 管理，自动 TTL 清理
7. **Job 持久化**：执行状态持久化，支持跨重启恢复

## 与 main 分支差异

当前 worktree 相对 origin/main 落后约 11 个 commits，execution 模块无显著差异（`actor.py` / `job_monitor_service.py` 已与 main 一致）。建议 rebase 后确认无额外变更。
