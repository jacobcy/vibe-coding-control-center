# PRD: Execution Plane — Aliases Worktree/Tmux Session Orchestration

## 1. Overview
将 `aliases` 明确为执行平面：负责 worktree/tmux 的实际操作、会话恢复和终端现场编排。

## 2. Problem Statement
控制平面承担执行动作会导致：
- 单会话能力上限冲突
- 终端上下文丢失
- 并行任务现场不可恢复

## 3. Product Goals
- 固化 aliases 为唯一执行入口
- 标准化 worktree 与 tmux 的映射命名
- 支持人类手动操作与 OpenClaw 技能自动操作两种模式

## 4. Non-Goals
- 不定义任务生命周期状态机
- 不实现 provider 流程语义
- 不替代 `vibe task` 的全局任务账本职责

## 5. Execution Surface
- worktree：创建/切换/清理/校验
- tmux：创建/连接/重命名/关闭/恢复
- 会话恢复：按 task/worktree/session hint 快速复原现场

## 6. Naming Conventions
- worktree 名：`wt-<owner>-<task-slug>`
- tmux session：`<agent>-<task-slug>`
- 冲突处理：自动追加短后缀

## 7. Human Mode vs OpenClaw Mode
- Human Mode：人工调用 alias 命令执行
- OpenClaw Mode：封装为技能，由 OpenClaw 代理调用相同命令面
- 两种模式必须写入同一执行结果结构

## 8. Execution Result Contract
执行后最小回写字段：
- `task_id`
- `resolved_worktree`
- `resolved_session`
- `executor` (`human|openclaw`)
- `timestamp`

## 9. Failure Handling
- worktree 创建失败：回滚临时分支并报错
- tmux 创建失败：保留 worktree，标记待恢复
- session 丢失：提供 `recover` 指令模板

## 10. Safety & Guardrails
- 禁止默认在 main 目录直接开发
- 清理命令需二次确认（或 `--force`）
- 日志输出避免泄漏敏感信息

## 11. Success Metrics
- 单任务现场恢复时间 < 30 秒
- 并行 5+ 会话时命名冲突率接近 0
- 执行平面错误可定位率 > 95%

## 12. Rollout Plan
- E1：梳理现有 aliases 能力矩阵
- E2：补齐缺失命令（仅当需要）
- E3：定义 OpenClaw skill 调用规范

## 13. Open Questions
- 是否需要统一 `wtrm` 与 tmux 清理的联动策略？
- OpenClaw 自动重试次数默认值多少合适？
