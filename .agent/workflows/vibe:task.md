---
name: "vibe:task"
description: Task-overview and registry-audit workflow that routes cross-worktree task analysis to the vibe-task skill.
category: Workflow
tags: [workflow, vibe, tasks, orchestration]
---

# vibe:task

**Input**: 运行 `/vibe-task` 触发，查看跨 worktree 的 flow/task 大盘、获得下一步该回哪个现场的建议，或处理 `roadmap <-> task` / task registry 修复。

## 定位

- `vibe:task` 是 task 总览与 registry 审计入口，只负责编排查询、委托 `vibe-task` skill，并返回建议或修复结论。
- 它是 task-centered audit，不处理 runtime / recovery audit。
- 具体 task 总览分析、roadmap-task 修复、execution spec 检查、用户确认点，都由 `vibe-task` skill 决定。
- runtime / `task <-> flow` 绑定修复不在此入口处理，应回到 `/vibe-check`。

## Steps

1. 回复用户：`我会先读取 task / roadmap 相关 shell 输出，再委托 vibe-task skill 生成总览或审计结论。`
2. 先确认当前请求属于：
   - 跨 worktree 的 flow/task 总览
   - `roadmap <-> task` / task registry 审计与修复
3. 委托 `skills/vibe-task/SKILL.md` 处理业务判断：
   - 读取 `vibe task` / `vibe task audit` 输出
   - 给出当前应优先回到的现场建议
   - 或输出 roadmap-task 修复建议与需确认项
4. 若问题其实属于 runtime / stale binding，停止并提示用户改走 `/vibe-check`。

## Boundary

- workflow 不承载 task 总览排序规则、registry 修复逻辑或 roadmap-task 映射判断。
- `vibe:task` 只处理 execution record / registry 语义，不承担 roadmap 版本规划。
- 所有共享状态修复动作都必须经由已有 shell 命令执行。
