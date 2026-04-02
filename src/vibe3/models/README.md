# Models

Pydantic 领域数据模型，定义系统中流转的核心数据结构。

## 职责

- 定义 Flow 状态模型（FlowState, ExecutionStatus）
- 定义 PR 模型（CreatePRRequest, PRResponse）
- 定义代码分析模型（FileSnapshot, StructureDiff, CallNode）
- 定义执行追踪模型（ExecutionStep, TraceOutput）
- 定义 Review/Agent 模型（AgentOptions, AgentResult）

## 关键组件

| 文件 | 职责 |
|------|------|
| flow.py | Flow 状态、执行状态 |
| pr.py | PR 请求/响应 |
| snapshot.py | 代码结构快照 |
| inspection.py | 代码分析结果 |
| trace.py | 执行追踪 |
| review.py | Review 模型 |
| review_runner.py | Agent 选项/结果 |
| orchestration.py | IssueInfo 编排模型 |
| plan.py | Plan 模型 |
| change_source.py | 变更源元数据 |
| coverage.py | Coverage 数据 |
| project_item.py | GitHub Project item |
| task_bridge.py | Task-review 桥接 |

## 依赖关系

- 依赖: (无内部依赖，纯数据定义)
- 被依赖: 几乎所有模块
