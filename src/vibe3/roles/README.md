# Roles

角色定义与执行模块，实现各角色的具体执行逻辑。

## 职责

- 角色定义：定义系统中所有角色及其触发条件
- 角色注册表：维护角色与触发标签的映射关系
- 角色执行：实现各角色的具体执行逻辑（manager, plan, run, review, governance, supervisor）
- 请求构建：构建各角色的执行请求和上下文

## 文件列表

统计时间：2026-07-01（当前 worktree 快照）

### 角色定义文件

| 文件 | 行数 | 职责 |
|------|------|------|
| `__init__.py` | ~130 | 公开 API 导出（lazy import + __all__ 一致性检查） |
| `definitions.py` | ~80 | 角色类型定义（`TriggerableRoleDefinition`、`IssueRoleSyncSpec`、`RoleDefinition`） |
| `registry.py` | ~95 | 角色注册表，维护标签到角色的映射（`LABEL_DISPATCH_ROLES`） |

### 角色实现文件

| 文件 | 行数 | 职责 |
|------|------|------|
| `manager.py` | ~320 | Manager 角色（状态机、协作调度） |
| `plan.py` | ~400 | Plan 角色（实现方案规划） |
| `run.py` | ~580 | Run 角色（方案执行） |
| `review.py` | ~450 | Review 角色（代码审查） |
| `governance.py` | ~430 | Governance 角色（系统治理建议） |
| `supervisor.py` | ~310 | Supervisor 角色（异常监控与恢复） |

### 角色辅助文件

| 文件 | 行数 | 职责 |
|------|------|------|
| `governance_factory.py` | ~120 | Governance 角色函数工厂（`build_default_governance_fns`） |
| `governance_utils.py` | ~90 | Governance 辅助函数（材料目录、查找） |
| `review_helpers.py` | ~70 | Review 辅助函数（`ReviewRunResult`） |
| `run_command.py` | ~150 | Run 命令构建 |
| `run_helpers.py` | ~100 | Run 辅助函数 |
| `run_request.py` | ~130 | Run 请求构建 |
| `scan_service.py` | ~250 | 执行层入口（调用 `execution.run_*`） |

**总计**：16 文件，约 5139 行

## 公开 APIs

核心入口（`vibe3.roles.X` lazy import，引用 `src/vibe3/roles/__init__.py`）：

| 入口 | 角色 | 主要消费者 |
|------|------|----------|
| `MANAGER_SYNC_SPEC / PLAN_SYNC_SPEC / RUN_SYNC_SPEC / REVIEW_SYNC_SPEC / SUPERVISOR_CLI_SYNC_SPEC` | `IssueRoleSyncSpec` 实例（角色自有 hooks 集合） | `commands/internal.py`，`roles/scan_service.py`，`execution/issue_role_sync_runner.py` |
| `build_manager_request / build_manager_sync_request` | Manager 角色请求构建 | `commands/internal.py` |
| `build_plan_request / build_plan_sync_request / build_plan_prompt / resolve_spec_plan_input / execute_spec_plan_sync / execute_spec_plan_async` | Plan 角色请求构建与执行 | `commands/plan.py` |
| `build_run_request / build_run_sync_request / dispatch_run_command_async / execute_manual_run / resolve_run_mode / resolve_skill_path / validate_run_prerequisites` | Run 角色请求构建与执行 | `commands/run.py` |
| `build_base_review_request / build_review_request / build_review_sync_request / execute_manual_review_sync / execute_manual_review_async / validate_review_prerequisites` | Review 角色请求构建与执行 | `commands/review.py` |
| `build_default_governance_fns / build_governance_request / build_governance_recipe / render_governance_prompt / load_governance_material_catalog` | Governance 角色请求构建 | `commands/scan.py`，`roles/scan_service.py` |
| `build_supervisor_apply_request / build_supervisor_cli_request / build_supervisor_cli_sync_request / iter_supervisor_identified_events / select_supervisor_events_for_dispatch` | Supervisor 角色请求构建 | `commands/internal.py`，`roles/scan_service.py` |
| `dispatch_governance_execution / dispatch_supervisor_execution` | 执行层入口（直接调用 `execution.run_governance_sync` / `run_issue_role_*`） | `commands/internal.py` |
| `fetch_supervisor_candidates / get_available_governance_materials / governance_material_exists / list_governance_materials` | 扫描辅助（GitHub 候选查询 + governance 材料目录） | `commands/scan.py` |
| `LABEL_DISPATCH_ROLES / build_label_dispatch_event` | 标签 → 角色注册表 | `domain/handlers/issue_state_dispatch.py`、`domain/handlers/manual_dispatch.py` |
| `TriggerableRoleDefinition / IssueRoleSyncSpec / RoleDefinition / RoleOutputContract / TriggerName` | 角色类型定义 | `definitions.py` 内部，`registry.py` |

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

> 关键约束：roles 不直接 import domain/execution（避免循环依赖），通过 `services/flow/factory.py`（`create_flow_manager`）与 `services/shared/events.py`（`emit_issue_failed`）间接调用。

## services 层依赖

- **domain → services**：`FlowManager` 直接依赖 `services.{flow,pr,issue,orchestra,shared}`；`QualifyGateService` 依赖 `services.{flow,issue,shared,task}`；`FailedGate` 依赖 `services.orchestra.ErrorTrackingService`。
- **roles → services**：roles 通过 `services/flow/factory.py`（`create_flow_manager`）与 `services/shared/events.py`（`emit_issue_failed`）间接消费 domain；直接依赖 `services.{flow,handoff,pr,task,shared,orchestra,issue}` 用于请求构建。
- **services 不反向依赖 domain/roles**：services 是 L3 基础层，仅通过 `services/shared/events.py` 发布 `IssueFailed` 事件（`publish` 来自 `vibe3.models`，非 domain 直接 import）。

## 依赖关系

### 依赖

- `execution`：执行协调器、容量服务、执行契约
- `clients`：Git 客户端、GitHub 客户端、SQLite 客户端
- `models`：编排配置、执行请求模型
- `config`：编排配置加载
- `domain`：事件发布、状态机
- `services`：Flow 服务、PR 服务、Task 服务、Handoff 服务
- `agents`：Agent 后端

### 被依赖

- `domain handlers`：事件处理器触发角色执行
- `commands`：命令层触发角色（如 vibe-run）

## 架构说明

### IssueRoleSyncSpec 设计

每个角色通过 `IssueRoleSyncSpec` 定义其执行 hooks：

```python
IssueRoleSyncSpec(
    role=RoleDefinition(name="plan", ...),
    pre_hooks=[...],
    post_hooks=[...],
    build_request=build_plan_sync_request,
)
```

### Label-based Dispatch

角色通过标签触发，实现松耦合调度：

```
Issue Label Change
    ↓
LABEL_DISPATCH_ROLES.lookup(label)
    ↓
build_label_dispatch_event()
    ↓
Domain Event
    ↓
Handler → ExecutionCoordinator
```

### 角色分工

- **Manager**：
  - 监控 issue 状态变化
  - 调度其他角色执行
  - 协调跨角色协作

- **Plan**：
  - 分析需求，规划实现方案
  - 输出实现计划（plan_ref）

- **Run**：
  - 执行实现方案
  - 编写代码、测试
  - 输出执行报告（report_ref）

- **Review**：
  - 审查代码变更
  - 评估质量、风险
  - 输出审查裁决（audit_ref）

- **Governance**：
  - 定期扫描系统状态
  - 发现问题并提出建议
  - 触发系统级改进

- **Supervisor**：
  - 监控执行状态
  - 处理异常情况
  - 触发恢复或重试

### scan_service 执行入口

`scan_service.py` 作为 roles 层到 execution 层的桥接：

```
dispatch_governance_execution()
  └─ execution.run_governance_sync()

dispatch_supervisor_execution()
  └─ execution.run_issue_role_*
```

### 关键设计

1. **标签驱动**：角色通过标签触发，避免硬编码依赖
2. **单一职责**：每个角色专注于一个阶段的工作
3. **状态隔离**：每次执行都在独立的 worktree 和 session 中
4. **可恢复性**：执行失败时保留现场，支持恢复
5. **协作模式**：Manager 协调多个角色协作完成复杂任务
6. **Spec 抽象**：`IssueRoleSyncSpec` 统一角色 hooks 定义

## 与 main 分支差异

当前 worktree 相对 origin/main 落后约 11 个 commits，roles 模块的主要差异：

1. **`scan_service.py` / `governance_factory.py` / `governance_utils.py` / `review_helpers.py` / `run_command.py` / `run_helpers.py` / `run_request.py`**：当前 worktree 已包含这些文件（`find` 已确认），与 main 一致。
2. **其他演进**：main 分支可能有额外的 refactoring 和 bug fix，建议 rebase 到 origin/main 后确认。
