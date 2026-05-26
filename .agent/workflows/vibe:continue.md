---
name: "vibe:continue"
description: Standard resume and execution entry workflow that routes current-flow task execution and backlog loading to the vibe-continue skill.
category: Workflow
tags: [workflow, vibe, execution, context, resume]
---

# vibe:continue

**Input**: 运行 `/vibe-continue`，恢复会话并建议下一步执行。

## 定位

- `vibe:continue` 是统一的会话恢复与执行入口，取代了已废弃的 `vibe:start`。
- 它负责判断当前 flow 的执行就绪状态，并将具体上下文读取、解释与继续建议委托给 `vibe-continue` skill。
- 它遵循“共享事实优先，本地 handoff 补充”原则。

## Steps

1. 回复用户：`正在恢复会话。我会先核查当前 flow 的共享事实与执行状态，再委托 vibe-continue skill 加载上下文并给出继续建议。`
2. 先读取当前 flow 与 task 事实，确认：
   - 当前 flow 是否绑定有效 task
   - task 是否具备 `plan_path`
   - 物理现场（branch/worktree）是否与 DB 一致
3. 委托 `skills/vibe-continue/SKILL.md` 处理核心逻辑：
   - 核查共享真源（`vibe3 flow show`）
   - 读取本地 handoff（`vibe3 handoff status`）
   - 核对当前 `git` 现场
   - 识别 `primary_issue_ref` 作为任务落点
4. 根据 skill 输出的 `Session Resume` 报告，引导用户按计划继续或处理 blocker。

## Boundary

- workflow 不承载会话恢复的具体业务判断，全部委托给 skill。
- 若缺失 execution spec 或 plan，workflow 负责引导回退到规划入口（如 `/vibe-new` 或 `/vibe-task`）。
- `/vibe-start` 已废弃，统一引导用户使用 `/vibe-continue`。
