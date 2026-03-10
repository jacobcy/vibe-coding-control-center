---
name: "Vibe: Done"
description: Finalize work after PR submission or worktree completion
category: Workflow
tags: [workflow, vibe, completion, archive]
---

# Vibe Done

**Input**: 运行 `/vibe-done` 触发，收口当前目录承载的 flow 所对应的任务。

## 执行要求

本命令用于在开发生命周期（Vibe Flow）收口时执行，特别是在执行完 `vibe flow pr` 或 `vibe flow done` CLI 命令后。

你的职责是：
1. **拦截调用**：识别到用户输入 `/vibe-done`。
2. **委托给 Skill**：直接调用并执行 `skills/vibe-done/SKILL.md`（若存在则走专用结算技能）。
3. **识别当前任务**：
   - 使用 shell 和共享真源获取当前状态与 `task_id`，不要依赖 worktree 本地缓存文件。
4. **验证大盘状态与推进收口**：
   - 通过 Shell API (如 `vibe task update --status completed`) 更新真源状态。
   - 确认是否已通过一切 Guard（Test/Review）。
5. **播报总结**：向用户总结本次已成功封板的任务与清理结果。
