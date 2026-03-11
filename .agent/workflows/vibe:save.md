---
name: "vibe:save"
description: Skill-backed workflow that routes session handoff and memory persistence to the vibe-save skill.
category: Workflow
tags: [workflow, vibe, memory, persistence]
---

# vibe:save

**Input**: 运行 `/vibe-save`，在阶段收口或会话结束时保存上下文。

## 定位

- `vibe:save` 是一个 `skill-backed workflow`。
- 它只负责会话保存入口，并将实际 handoff 与 memory 写入委托给 `vibe-save` skill。

## Steps

1. 回复用户：`我会先读取当前 task / flow 事实，再委托 vibe-save skill 写回 handoff 与 memory。`
2. 委托 `skills/vibe-save/SKILL.md` 处理实际保存动作。
3. 返回已保存内容的简短摘要。

## Boundary

- workflow 不直接写 `.agent/context/*`。
- 若需要同步共享状态，只能通过 shell API 完成，不得在 workflow 中定义写入策略。
