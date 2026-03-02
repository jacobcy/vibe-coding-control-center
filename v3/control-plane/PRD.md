# PRD: Control Plane Project

## 1. 项目定义

Control Plane 只负责跨 worktree 的任务生命周期与全局任务账本。

## 2. 目标

- 统一任务状态机
- 提供 provider 无关的任务元数据
- 提供跨 worktree 可观测视图

## 3. 非目标

- 不执行 worktree/tmux 命令
- 不解析 provider 内部流程

## 4. 核心模型

- `task_id`
- `status`
- `owner`
- `provider`
- `provider_ref`
- `worktree_hint`
- `updated_at`

## 5. 接口输入输出

输入：来自流程/执行平面的最小回写。  
输出：统一任务状态与执行意图。

## 6. 验收标准

- 脱离具体 provider 仍可运行
- 脱离具体 aliases 实现仍可表达任务状态
