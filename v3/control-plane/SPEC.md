# Control Plane SPEC (Canonical)

## 1. 定位
Control Plane 负责跨 worktree 的任务生命周期与全局状态账本。

## 2. 迁移声明
- 本项目是 V2 -> V3 架构迁移，不是完全改写。
- 允许复用/拷贝 V2 逻辑，但 V3 阶段只在 `v3/` 目录改写规范。

## 3. 命令规范（Canonical）
- 使用 `vibe task`（不用 `vibe tasks`）
- 使用 `vibe task create`（不用 `vibe task add`）
- 使用 `vibe flow start`（不用 `vibe new`）

## 4. 状态机
`todo -> in_progress -> blocked -> done -> archived`

## 5. 最小字段
- `task_id`
- `title`
- `status`
- `owner`
- `provider`
- `provider_ref`
- `worktree_hint`
- `updated_at`

## 6. 边界
- 不执行 worktree/tmux 命令
- 不解析 provider 内部流程步骤

## 7. 本目录规范文件
- `SPEC.md`：本文件（唯一规范入口）
- `PLAN.md`：迁移执行计划
- 其他 md：历史迁移稿，保留不删
