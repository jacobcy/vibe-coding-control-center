---
name: "Vibe: Task"
description: View flow/task overview across worktrees and handle task-registry or roadmap-task audit and repair work, not roadmap prioritization or runtime repair.
category: Workflow
tags: [workflow, vibe, tasks, overview]
---

# Vibe Task Overview And Repair

**Input**: 运行 `/vibe-task` 触发，查看跨 worktree 的 flow/task 大盘、获得下一步该回哪个现场的建议，或处理 `roadmap <-> task` / task registry 修复。

## 执行要求

本命令直接对应 `vibe-task` 技能，你的职责是：
1. **拦截调用**：识别到用户输入 `/vibe-task` 或类似意图。
2. **委托给 Skill**：直接调用并执行 `skills/vibe-task/SKILL.md` 技能。
3. **输出结果**：将底层 CLI `bin/vibe task` 的输出进行解释并报告，推荐优先回到的 flow/现场并指出其当前承载目录，或说明 roadmap-task 修复建议。
