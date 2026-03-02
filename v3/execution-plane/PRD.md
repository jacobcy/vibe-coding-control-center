# PRD: Execution Plane Project

## 1. 项目定义

Execution Plane 负责 worktree/tmux 的实际操作、会话恢复和终端现场编排。

## 2. 目标

- 统一 aliases 执行面
- 支持 human 与 openclaw skill 两种执行者
- 将执行结果标准化回写控制平面

## 3. 非目标

- 不定义任务生命周期状态机
- 不决定 provider 路由策略

## 4. 核心能力

- worktree create/switch/cleanup
- tmux new/attach/kill/recover
- 会话命名规范与冲突处理

## 5. 接口输入输出

输入：control plane 执行意图。  
输出：`resolved_worktree`, `resolved_session`, `executor`, `timestamp`。

## 6. 验收标准

- 单任务现场恢复 < 30 秒
- 并行多会话稳定可恢复
