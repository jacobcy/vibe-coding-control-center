# Models

Pydantic 领域数据模型，定义系统中流转的核心数据结构。

## 文件列表

| 文件 | 行数 | 职责 |
|------|------|------|
| flow.py | 409 | Flow 状态、IssueLink、TimelineEvent |
| orchestra_config.py | 319 | Orchestra 配置模型（执行策略、并发控制） |
| domain_events.py | 263 | 领域事件定义（DomainEvent、FlowCompleted 等） |
| orchestration.py | 242 | IssueInfo 编排模型、IssueState、StateTransition |
| audit_decision.py | 238 | 审计决策模型 |
| snapshot.py | 203 | 代码结构快照（FileSnapshot、StructureDiff） |
| audit_observation.py | 196 | 审计观察模型 |
| event_bus.py | 164 | 事件总线（EventPublisher、subscribe） |
| job.py | 188 | Job 模型（JobEnvelope、JobResult） |
| inspection.py | 173 | 代码分析结果（CallNode、CommandInspection） |
| trace.py | 155 | 执行追踪（ExecutionStep、TraceOutput） |
| pr.py | 185 | PR 请求/响应模型（CreatePRRequest、PRState） |
| adapter_manifest.py | 82 | Adapter 清单模型 |
| review.py | 81 | Review 模型、ReviewResult |
| review_runner.py | 53 | Agent 选项、Agent 结果 |
| coordination_truth.py | 108 | 协调真值模型 |
| audit_suggestion.py | 155 | 审计建议模型 |
| plan.py | 71 | Plan 模型、PlanSpecInput |
| actor_utils.py | 56 | Actor 工具函数和常量 |
| task_bridge.py | 71 | Task-review 桥接模型 |
| coverage.py | 76 | Coverage 数据 |
| execution_request.py | 49 | 执行请求模型 |
| state_machine.py | 48 | 状态机标签和转换验证 |
| change_source.py | 47 | 变更源元数据 |
| pr_analysis.py | 48 | PR 分析结果 |
| runtime_session.py | 32 | 运行时会话模型 |
| verdict.py | 43 | Verdict 记录、VerdictRecord |
| dead_code.py | 34 | 死代码检测结果 |
| issue_body.py | 38 | FlowStateProjection |
| worktree.py | 11 | WorktreeRequirement |
| queue_entry.py | 18 | QueueEntry |
| data_source.py | 20 | DataSource |
| handoff.py | 21 | Handoff 记录模型 |
| check_result.py | 13 | CheckResult |
| execution_handle.py | 15 | AsyncExecutionHandle |
| dispatch.py | 11 | DispatchExclusion |
| session_types.py | 7 | SessionRole |
| prompt_meta.py | 6 | PromptContextMode |
| verdict_types.py | 9 | VerdictValue |
| branch_convention.py | 86 | BranchConvention |
| __init__.py | 424 | 公共 API 导出（lazy import） |

截至 2026-06，总计 41 文件，约 4468 行代码。

## 架构说明

Models 模块按职责分为多个类别：

### 1. 编排与配置（Orchestration & Config）

- **orchestra_config.py**: 执行策略、并发控制、manager 配置（OrchestraConfig, GovernanceConfig 等）
- **orchestration.py**: IssueInfo、IssueState、StateTransition、ALLOWED_TRANSITIONS
- **plan.py**: PlanRequest、PlanScope、PlanSpecInput

### 2. Flow 与状态（Flow & State）

- **flow.py**: FlowState、FlowEvent、IssueLink、TimelineEvent
- **state_machine.py**: STATE_LABEL_META、VIBE_TASK_LABEL、can_transition、validate_transition
- **verdict.py**: VerdictRecord
- **verdict_types.py**: VerdictValue

### 3. 领域事件（Domain Events）

- **domain_events.py**: DomainEvent、ControlPlaneEventPublished、ExecutorDispatchIntent、FlowBlocked、FlowCompleted、IssueFailed、ManagerDispatchIntent、ManualPlanIntent、ManualReviewIntent、ManualRunIntent、PlannerDispatchIntent、PolicyChanged、PRMerged、ReviewerDispatchIntent、SupervisorIssueIdentified、WebhookIssueClosed、WebhookIssueUpdated、WebhookLabelChanged、WebhookPRMerged、WebhookPRReviewed

### 4. 事件总线（Event Bus）

- **event_bus.py**: EventHandler、EventPublisher、PublishHook、get_publisher、publish、publish_and_wait、subscribe

### 5. 审计（Audit）

- **audit_decision.py**: AuditDecision
- **audit_observation.py**: AuditObservation（ObservationSourceWindow 为内部模型）
- **audit_suggestion.py**: AuditSuggestion

### 6. Job

- **job.py**: CommandType、JobContext、JobEnvelope、JobResult、JobSource

### 7. 代码分析（Code Analysis）

- **snapshot.py**: FileSnapshot、FunctionSnapshot、ModuleSnapshot、StructureSnapshot、FileChange、ModuleChange、DependencyChange、DependencyEdge、StructureDiff、StructureMetrics、DiffSummary、DiffWarning
- **inspection.py**: CallNode、CommandInspection
- **coverage.py**: CoverageReport、LayerCoverage
- **dead_code.py**: DeadCodeFinding、DeadCodeReport

### 8. 执行追踪（Execution Trace）

- **trace.py**: ExecutionStep、TraceOutput、format_result_entries

### 9. 执行请求（Execution Request）

- **execution_request.py**: ExecutionLaunchResult、ExecutionRequest
- **execution_handle.py**: AsyncExecutionHandle

### 10. PR 相关（PR）

- **pr.py**: CreatePRRequest、PRMetadata、PRResponse、PRState、UpdatePRRequest、VersionBumpResponse、VersionBumpType、CICheck
- **pr_analysis.py**: CommitInfo、CriticalFileInfo、PRCriticalAnalysis

### 11. Review 相关（Review）

- **review.py**: ReviewRequest、ReviewScope
- **review_runner.py**: AgentOptions、AgentResult

### 12. 变更源（Change Source）

- **change_source.py**: BranchSource、ChangeSource、ChangeSourceType、CommitSource、PRSource、UncommittedSource

### 13. 其他（Others）

- **coordination_truth.py**: CoordinationTruth
- **data_source.py**: DataSource
- **check_result.py**: CheckResult
- **dispatch.py**: DispatchExclusion
- **prompt_meta.py**: PromptContextMode
- **session_types.py**: SessionRole
- **queue_entry.py**: QueueEntry
- **worktree.py**: WorktreeRequirement
- **adapter_manifest.py**: AdapterManifest、AdapterResource
- **branch_convention.py**: BranchConvention
- **actor_utils.py**: normalize_actor、ACTOR_ALIAS_MAP、DISPLAY_PLACEHOLDER_ACTORS、PLACEHOLDER_ACTORS

## 公共 API

`__init__.py` 导出以下 121 个符号（通过 lazy import）：

### 编排与配置

- **OrchestraConfig**: Orchestra 主配置
- **GovernanceConfig**: Governance 配置
- **PeriodicCheckConfig**: Periodic check 配置
- **QueueRefreshConfig**: Queue refresh 配置
- **SupervisorHandoffConfig**: Supervisor handoff 配置
- **IssueInfo**: Issue 信息模型
- **IssueState**: Issue 状态枚举
- **StateTransition**: 状态转换记录
- **ALLOWED_TRANSITIONS**: 允许的状态转换集合
- **FORBIDDEN_TRANSITIONS**: 禁止的状态转换集合
- **PlanRequest**: Plan 请求模型
- **PlanScope**: Plan 范围模型
- **PlanSpecInput**: Plan spec 输入

### Flow 与状态

- **FlowEvent**: Flow 事件
- **FlowState**: Flow 状态
- **FlowStatusResponse**: Flow 状态响应
- **FlowStateProjection**: Flow 状态投影
- **IssueLink**: Issue 链接记录
- **MainBranchProtectedError**: Main branch 保护错误
- **TimelineEvent**: 时间线事件
- **STATE_LABEL_META**: State label 元数据
- **VIBE_TASK_LABEL**: Vibe task 标签常量
- **can_transition**: 状态转换验证函数
- **validate_transition**: 状态转换验证函数（抛异常）
- **VerdictRecord**: Verdict 记录
- **VerdictValue**: Verdict 值枚举

### 领域事件

- **DomainEvent**: 领域事件基类
- **ControlPlaneEventPublished**: Control plane 事件发布
- **ExecutorDispatchIntent**: Executor dispatch 意图
- **FlowBlocked**: Flow 阻塞事件
- **FlowCompleted**: Flow 完成事件
- **IssueFailed**: Issue 失败事件
- **ManagerDispatchIntent**: Manager dispatch 意图
- **ManualPlanIntent**: Manual plan 意图
- **ManualReviewIntent**: Manual review 意图
- **ManualRunIntent**: Manual run 意图
- **PlannerDispatchIntent**: Planner dispatch 意图
- **PolicyChanged**: Policy 变更事件
- **PRMerged**: PR 合并事件
- **ReviewerDispatchIntent**: Reviewer dispatch 意图
- **SupervisorIssueIdentified**: Supervisor issue 识别事件
- **WebhookIssueClosed**: Webhook issue 关闭事件
- **WebhookIssueUpdated**: Webhook issue 更新事件
- **WebhookLabelChanged**: Webhook label 变更事件
- **WebhookPRMerged**: Webhook PR 合并事件
- **WebhookPRReviewed**: Webhook PR review 事件

### 事件总线

- **EventHandler**: Event handler 类型
- **EventPublisher**: Event publisher 类
- **PublishHook**: Publish hook 类型
- **get_publisher**: 获取 publisher 实例
- **publish**: 发布事件函数
- **publish_and_wait**: 发布事件并等待处理完成
- **subscribe**: 订阅事件

### 审计

- **AuditDecision**: 审计决策
- **AuditObservation**: 审计观察
- **AuditSuggestion**: 审计建议

### Job

- **CommandType**: Command 类型枚举
- **JobContext**: Job 上下文
- **JobEnvelope**: Job 信封
- **JobResult**: Job 结果
- **JobSource**: Job 来源

### 代码分析

- **CallNode**: 调用节点
- **CommandInspection**: Command 检查结果
- **FileSnapshot**: 文件快照
- **FunctionSnapshot**: 函数快照
- **ModuleSnapshot**: 模块快照
- **StructureSnapshot**: 结构快照
- **FileChange**: 文件变更
- **ModuleChange**: 模块变更
- **DependencyChange**: 依赖变更
- **DependencyEdge**: 依赖边
- **StructureDiff**: 结构差异
- **StructureMetrics**: 结构度量
- **DiffSummary**: Diff 摘要
- **DiffWarning**: Diff 警告
- **CoverageReport**: 覆盖率报告
- **LayerCoverage**: 层覆盖率
- **DeadCodeFinding**: 死代码发现
- **DeadCodeReport**: 死代码报告

### 执行追踪

- **ExecutionStep**: 执行步骤
- **TraceOutput**: Trace 输出
- **format_result_entries**: 格式化结果条目

### 执行请求

- **ExecutionLaunchResult**: 执行启动结果
- **ExecutionRequest**: 执行请求
- **AsyncExecutionHandle**: 异步执行句柄

### PR 相关

- **CreatePRRequest**: 创建 PR 请求
- **PRMetadata**: PR 元数据
- **PRResponse**: PR 响应
- **PRState**: PR 状态
- **UpdatePRRequest**: 更新 PR 请求
- **VersionBumpResponse**: 版本 bump 响应
- **VersionBumpType**: 版本 bump 类型
- **CICheck**: CI check
- **CommitInfo**: Commit 信息
- **CriticalFileInfo**: 关键文件信息
- **PRCriticalAnalysis**: PR 关键分析

### Review 相关

- **ReviewRequest**: Review 请求
- **ReviewScope**: Review 范围
- **AgentOptions**: Agent 选项
- **AgentResult**: Agent 结果

### 变更源

- **BranchSource**: Branch 变更源
- **ChangeSource**: 变更源基类
- **ChangeSourceType**: 变更源类型
- **CommitSource**: Commit 变更源
- **PRSource**: PR 变更源
- **UncommittedSource**: Uncommitted 变更源

### 其他

- **CoordinationTruth**: 协调真值
- **DataSource**: 数据源
- **CheckResult**: Check 结果
- **DispatchExclusion**: Dispatch 排除项
- **PromptContextMode**: Prompt 上下文模式
- **SessionRole**: Session 角色
- **QueueEntry**: Queue 条目
- **WorktreeRequirement**: Worktree 需求
- **AdapterManifest**: Adapter 清单
- **AdapterResource**: Adapter 资源
- **BranchConvention**: Branch 约定
- **normalize_actor**: Actor 归一化函数
- **ACTOR_ALIAS_MAP**: Actor 别名映射
- **DISPLAY_PLACEHOLDER_ACTORS**: 显示用 placeholder actors
- **PLACEHOLDER_ACTORS**: Placeholder actors

## 内部依赖

```
models/
├── 无依赖层（纯数据定义）
│   ├── orchestra_config.py
│   ├── orchestration.py
│   ├── inspection.py
│   ├── snapshot.py
│   ├── trace.py
│   ├── pr.py
│   ├── plan.py
│   ├── review_runner.py
│   ├── coverage.py
│   ├── pr_analysis.py
│   ├── change_source.py
│   ├── verdict.py
│   ├── verdict_types.py
│   ├── dead_code.py
│   ├── runtime_session.py
│   └── 大部分其他模型文件
└── 依赖层（引用其他 models）
    ├── flow.py → verdict.py (VerdictRecord)
    ├── handoff.py → review_runner.py (AgentOptions)
    ├── review.py → snapshot.py (StructureDiff)
    └── event_bus.py → domain_events.py (DomainEvent)
```

**循环依赖检查**: ✅ 无循环依赖

**外部依赖**:
- vibe3.exceptions: VibeError 系列（部分模型使用）

**被依赖**:
- ~251 个文件引用，覆盖 adapters/agents/analysis/clients/commands/config/domain/environment/execution/orchestra/roles/runtime/server/services/ui/utils 等所有模块

## 设计原则

- **纯数据定义**: Models 模块保持纯数据定义，不包含业务逻辑
- **Pydantic BaseModel**: 所有模型均为 Pydantic BaseModel，提供类型验证和序列化能力
- **Lazy Import**: `__init__.py` 使用 lazy import 避免循环依赖
- **领域驱动**: 按领域划分模型（Flow、PR、Review、Audit 等）
- **类型安全**: 所有字段都有明确的类型注解
