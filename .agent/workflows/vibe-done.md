---
name: "Vibe: Done"
description: Finalize work after PR submission or worktree completion
category: Workflow
tags: [workflow, vibe, completion, archive]
---

# Vibe Done

**Input**: 运行 `/vibe-done` 触发，收口已经 merge 的当前 flow / task。

## 执行要求

本命令用于开发生命周期的最终收口阶段，只处理 `merged` 之后的动作，不替代 `/vibe-integrate`。

你的职责是：
1. **拦截调用**：识别到用户输入 `/vibe-done`。
2. **委托给 Skill**：直接调用并执行 `skills/vibe-done/SKILL.md`（若存在则走专用结算技能）。
3. **识别当前任务**：
   - 使用 shell 获取当前状态，或从 `.vibe/current-task.json` 中提取 `task_id`。
4. **验证大盘状态与推进收口**：
   - 先确认当前 flow 已经 `open + had_pr` 且 PR 已合并。
   - 再通过 Shell API（如 `vibe task update --status completed`）推进共享真源收口。
   - `vibe flow done` 只负责 flow 关闭与 branch 清理，不负责 task / issue 关闭编排。
5. **播报总结**：向用户总结本次已成功封板的任务与清理结果。
