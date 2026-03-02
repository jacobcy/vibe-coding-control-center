---
description: 提交 PR 或结束本地工作树后用于收尾工作，一键流转到 Completed/Archived 状态。
---

# Vibe Done

**Input**: 运行 `/vibe-done` 触发，收口当前 Worktree 绑定的任务。

## 执行要求

本命令用于在开发生命周期（Vibe Flow）收口时执行，特别是在执行完 `vibe flow pr` 或 `vibe flow done` CLI 命令后。

你的职责是：
1. **拦截调用**：识别到用户输入 `/vibe-done`。
2. **委托给 Skill**：直接调用并执行 `skills/vibe-done/SKILL.md`（若存在则走专用结算技能）或者，如果本系统未启用专门的分支收尾技能，你可以临时作为任务结算编排器工作。
3. **识别当前任务**：
   - 读取 `.vibe/current-task.json` 确定当前绑定的 `task_id`
4. **验证大盘状态与推进收口**：
   - 读取 `$(git rev-parse --git-common-dir)/vibe/registry.json` 和 `tasks/<task_id>/task.json`。
   - 确认是否已通过一切 Guard（Test/Review）。
   - 主动写入将当前 `status` 从 `in_progress` 设置为了 `completed` 或 `archived`。
   - 如果对应 Worktree 在 `worktrees.json` 中，更新其状态或者从 active 列表平滑安全移除。
5. **播报总结**：向用户总结本次已成功封板的任务与清理结果。
