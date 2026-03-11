---
name: "vibe:new"
description: Planning-entry workflow that routes intake to the vibe-new skill and stops after plan/task binding is ready.
category: Workflow
tags: [workflow, vibe, planning, orchestration]
---

# vibe:new

**Input**: 运行 `/vibe-new <goal-or-slug> [--save-unstash]`，进入规划入口。

## 定位

- `vibe:new` 是 workflow 层入口，只负责规划阶段的编排与委托。
- 具体 intake、plan、task 绑定、handoff 与 flow 纪律，统一委托 `vibe-new` skill。
- 本入口完成条件只有一个：plan 已生成，task 已与 plan 绑定，然后停止。

## Steps

1. 回复用户：`进入规划模式。我会先确认目标来源，再委托 vibe-new skill 完成 intake、plan 和 task 绑定。`
2. 先检查 roadmap / flow / handoff 上下文，确认当前目标来自现有 task、handoff blocker、roadmap item 还是用户显式输入。
3. 委托 `skills/vibe-new/SKILL.md` 处理业务判断：
   - 选择 intake 来源
   - 必要时联动 `vibe-issue`、`vibe-roadmap`、`writing-plans`
   - 创建或更新 task，并写入 `spec_standard/spec_ref`
   - 需要时创建新的逻辑 flow
4. 当 `plan + task binding` 已就绪后，立即停止，并提示用户改用 `/vibe-start`。

## Boundary

- workflow 只编排，不承载 handoff mode、task gate、plan 生成细则。
- `vibe:new` 不直接修改业务代码。
- 未经人类明确授权，不得新建物理 worktree；默认使用当前目录里的 `vibe flow new` 建立新的逻辑现场。
