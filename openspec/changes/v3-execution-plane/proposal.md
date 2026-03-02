## Why

V2 架构中，控制平面承担执行动作导致三个核心问题：
1. **单会话能力上限冲突**：一个 agent 无法同时管理多个并行任务
2. **终端上下文丢失**：任务切换时会话状态无法保存和恢复
3. **并行任务现场不可恢复**：缺乏标准化的 worktree/tmux 映射机制

现在需要将执行职责明确分离为独立平面，固化 `aliases` 为唯一执行入口，支持多 agent 并行开发场景。

## What Changes

- **固化执行平面职责**：明确 aliases 负责所有 worktree/tmux 实际操作
- **标准化命名规范**：统一 worktree 和 tmux session 命名约定（`wt-<owner>-<task-slug>` 和 `<agent>-<task-slug>`）
- **双模式支持**：支持 Human Mode（人工调用）和 OpenClaw Mode（技能自动调用）两种执行方式
- **执行结果回写**：建立标准化执行结果契约，回写 `resolved_worktree`、`resolved_session`、`executor`、`timestamp`
- **会话恢复能力**：按 task/worktree/session hint 快速复原开发现场（目标 < 30 秒）
- **冲突处理机制**：自动处理命名冲突（追加短后缀）

## Capabilities

### New Capabilities

- `execution-plane-worktree`: worktree 生命周期管理（create/switch/cleanup/validate）
- `execution-plane-tmux`: tmux 会话管理（new/attach/kill/rename/recover）
- `execution-plane-session-recovery`: 多会话现场恢复能力（基于 task/worktree/session hint）
- `execution-plane-execution-contract`: 执行结果标准化回写契约（task_id, resolved_worktree, resolved_session, executor, timestamp）

### Modified Capabilities

无（这是新架构能力，不修改现有 specs）

## Impact

**代码影响**：
- `config/aliases/worktree.sh`：增强 worktree 命令，添加命名规范和冲突处理
- `config/aliases/tmux.sh`：增强 tmux 命令，支持会话恢复和标准化命名
- 新增 `config/aliases/execution-contract.sh`：执行结果回写逻辑
- 新增 `skills/execution-plane/`：OpenClaw skill 封装

**API/接口影响**：
- 新增 Execution Result Contract API（供 control plane 调用）
- 新增 OpenClaw skill 调用规范

**依赖影响**：
- 依赖 V3 control plane 提供执行意图（task_id, worktree_hint, session_hint）
- 依赖 tmux 和 git worktree 能力

**系统影响**：
- 改变开发者工作流：从单会话手动管理 → 多会话标准化管理
- 提升并行任务开发效率（目标：单任务恢复 < 30 秒，并行 5+ 会话冲突率接近 0）
