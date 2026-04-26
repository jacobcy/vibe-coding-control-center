---
name: "vibe:continue"
description: Skill-backed workflow that routes session resume and backlog loading to the vibe-continue skill.
category: Workflow
tags: [workflow, vibe, context, resume]
---

# vibe:continue

**Input**: 运行 `/vibe-continue`，恢复上次会话或中断任务的上下文。

## 定位

- `vibe:continue` 是一个 `skill-backed workflow`。
- 它负责恢复会话入口，并将具体上下文读取与解释委托给 `vibe-continue` skill。

## Steps

1. 回复用户：`我会先确认当前执行代理身份，再委托 vibe-continue skill 加载任务与记忆上下文。`
2. 必要时读取 shell 上下文，例如当前 agent 身份与当前现场事实。
3. 委托 `skills/vibe-continue/SKILL.md` 处理：
   - 运行 `vibe3 handoff status`
   - 读取相关 memory
   - 输出 backlog 和当前治理阶段
4. 返回恢复结果，并等待用户指示下一步。

## Boundary

- workflow 不承载会话恢复的业务判断。
- 若需要具体 backlog 解释或修复建议，统一由 `vibe-continue` skill 负责。
