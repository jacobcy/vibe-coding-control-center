# Execution Plane SPEC (Canonical)

## 1. 定位
Execution Plane 负责 worktree/tmux 的实际执行与会话恢复。

## 2. 迁移声明
- 本项目是架构迁移，复用 V2 aliases 能力，不重写执行逻辑理念。
- V3 迁移阶段仅改写 `v3/` 内规范与计划文档。

## 3. 执行模式
- Human Mode：人工调用 aliases
- OpenClaw Mode：通过 OpenClaw skill 调用同一命令面

## 4. 命名规范
- worktree：`wt-<owner>-<task-slug>`
- session：`<agent>-<task-slug>`

## 5. 执行回写契约
- `task_id`
- `resolved_worktree`
- `resolved_session`
- `executor`
- `timestamp`

## 6. 边界
- 不维护任务状态机
- 不做 provider 路由决策

## 7. 本目录规范文件
- `SPEC.md`：本文件（唯一规范入口）
- `PLAN.md`：迁移执行计划
- 其他 md：历史迁移稿，保留不删
