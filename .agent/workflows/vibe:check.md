---
name: "vibe:check"
description: Runtime-audit workflow that routes task-flow consistency analysis and deterministic repair to the vibe-check skill.
category: Workflow
tags: [workflow, vibe, verification, orchestration]
---

# vibe:check

**Input**: 运行 `/vibe-check`，检查当前 runtime / task-flow 一致性，并在安全时交给 `vibe-check` skill 修复。

## 定位

- `vibe:check` 是 runtime 审计入口，只负责编排 shell 审计、委托 `vibe-check` skill，并交付结果。
- 具体问题分类、可自动修复项、需确认项、shell 能力缺口，都由 `vibe-check` skill 决定。
- `roadmap <-> task` 对应关系不在此入口处理，应回到 `/vibe-task`。

## Steps

1. 回复用户：`我会先读取 shell 审计结果，再委托 vibe-check skill 解释 runtime 问题并处理可确定修复项。`
2. 先通过 shell 获取审计事实，确认问题是否属于 `task <-> flow` / runtime 一致性。
3. 委托 `skills/vibe-check/SKILL.md` 处理业务判断：
   - 读取审计输出
   - 分类为可自动修复、需确认、能力缺口
   - 仅通过 shell 原子命令执行安全修复
4. 返回审计结果、已执行修复和后续建议；若问题属于 `roadmap <-> task`，提示用户改走 `/vibe-task`。

## Boundary

- workflow 不承载修复分类规则或具体 shell 策略。
- `vibe:check` 只处理 runtime / task-flow 一致性，不处理 roadmap 规划或 task registry 语义修复。
- 共享状态写入只能通过 shell API 完成。
