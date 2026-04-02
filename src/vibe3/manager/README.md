# Manager

Orchestra 的执行代理层，负责将 issue 映射到 flow，构建和执行 agent 命令，管理 worktree 生命周期。

## 职责

- Issue → Flow 映射与创建
- Agent 命令构建（plan/review/run）
- Worktree 生命周期管理（创建、复用、回收）
- 命令执行与事件记录
- 执行结果处理

## 关键组件

| 文件 | 职责 |
|------|------|
| flow_manager.py | Issue-to-flow 映射和 flow 创建 |
| command_builder.py | 构建可执行的 agent 命令 |
| manager_executor.py | 命令执行 + 事件日志 |
| worktree_manager.py | Worktree 创建/查找/回收 |
| result_handler.py | Agent 执行结果处理 |
| prompts.py | Manager 专用 prompt 构建 |

## 与 orchestra 的关系

- **orchestra**: 决策层 — 决定对 issue 做什么（分诊、调度）
- **manager**: 执行层 — 执行 orchestra 的决策（创建 flow、跑 agent、管 worktree）

## 依赖关系

- 依赖: services (FlowService), clients (Git/GitHub), agents, models, config
- 被依赖: orchestra (dispatcher 调用 manager)
