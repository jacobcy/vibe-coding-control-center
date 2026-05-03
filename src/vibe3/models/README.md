# Models

Pydantic 领域数据模型，定义系统中流转的核心数据结构。

## 文件列表

| 文件 | 行数 | 职责 |
|------|------|------|
| flow.py | 366 | Flow 状态、执行状态、状态转换 |
| orchestra_config.py | 275 | Orchestra 配置模型（执行策略、并发控制） |
| orchestration.py | 235 | IssueInfo 编排模型、任务编排元数据 |
| inspection.py | 173 | 代码分析结果（CallNode、CommandInspection） |
| snapshot.py | 171 | 代码结构快照（FileSnapshot、StructureDiff） |
| trace.py | 153 | 执行追踪（ExecutionStep、TraceOutput） |
| pr.py | 152 | PR 请求/响应模型 |
| review.py | 103 | Review 模型、ReviewResult |
| task_bridge.py | 74 | Task-review 桥接模型 |
| plan.py | 71 | Plan 模型、计划元数据 |
| review_runner.py | 53 | Agent 选项、Agent 结果 |
| project_item.py | 52 | GitHub Project item |
| coverage.py | 52 | Coverage 数据 |
| pr_analysis.py | 48 | PR 分析结果 |
| change_source.py | 47 | 变更源元数据 |
| verdict.py | 42 | Verdict 记录、裁决结果 |
| __init__.py | 37 | 公共 API 导出 |
| dead_code.py | 34 | 死代码检测结果 |
| runtime_session.py | 32 | 运行时会话模型 |
| handoff.py | 21 | Handoff 记录模型 |

**总计**: 20 文件，2191 行代码

## 架构说明

Models 模块按职责分为 4 个类别：

### 1. 编排与配置（Orchestration & Config）
- **orchestra_config.py**: 执行策略、并发控制、manager 配置
- **orchestration.py**: IssueInfo、任务编排元数据
- **plan.py**: Plan 模型、计划元数据

### 2. 状态与追踪（State & Trace）
- **flow.py**: FlowState、ExecutionStatus、状态转换
- **trace.py**: ExecutionStep、TraceOutput、执行追踪
- **verdict.py**: VerdictRecord、裁决结果
- **handoff.py**: Handoff 记录模型

### 3. 代码分析（Code Analysis）
- **snapshot.py**: FileSnapshot、StructureDiff、结构快照
- **inspection.py**: CallNode、CommandInspection、代码分析
- **coverage.py**: Coverage 数据
- **dead_code.py**: 死代码检测

### 4. 集成与桥接（Integration & Bridge）
- **pr.py**: PR 请求/响应模型
- **review.py**: Review 模型、ReviewResult
- **review_runner.py**: Agent 选项、Agent 结果
- **task_bridge.py**: Task-review 桥接
- **pr_analysis.py**: PR 分析结果
- **project_item.py**: GitHub Project item
- **change_source.py**: 变更源元数据
- **runtime_session.py**: 运行时会话

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
│   ├── project_item.py
│   ├── coverage.py
│   ├── pr_analysis.py
│   ├── change_source.py
│   ├── verdict.py
│   ├── dead_code.py
│   └── runtime_session.py
└── 依赖层（引用其他 models）
    ├── flow.py → verdict.py (VerdictRecord)
    ├── handoff.py → review_runner.py (AgentOptions)
    └── review.py → snapshot.py (StructureDiff)
```

**循环依赖检查**: ✅ 无循环依赖

**被依赖**: 几乎所有模块（services、commands、agents、analysis）

## 公共 API

`__init__.py` 导出以下模型：

**代码分析**:
- `CallNode`, `CommandInspection` (from inspection)
- `FileSnapshot`, `FunctionSnapshot`, `ModuleSnapshot`, `StructureSnapshot`
- `FileChange`, `ModuleChange`, `DependencyChange`
- `StructureDiff`, `StructureMetrics`, `DiffSummary`, `DiffWarning`
- `DependencyEdge` (from snapshot)

**执行追踪**:
- `ExecutionStep`, `TraceOutput` (from trace)

**设计原则**: Models 模块保持纯数据定义，不包含业务逻辑。所有模型均为 Pydantic BaseModel，提供类型验证和序列化能力。
