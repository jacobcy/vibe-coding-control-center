---
name: "vibe:new"
description: Planning-entry workflow that routes intake to the vibe-new skill and stops after bootstrap is ready.
category: Workflow
tags: [workflow, vibe, planning, orchestration]
---

# vibe:new

**Input**: 运行 `/vibe-new <goal-or-slug> [--save-unstash]`，进入规划入口。

## 职责

编排 vibe-new skill 完成人机协作准备，不承诺 plan 和 task 绑定都由 workflow 层完成。

## Steps

1. 回复用户：`进入规划模式。我会先确认目标来源，再委托 vibe-new skill 选择 workflow 并完成基础设施 bootstrap。`
2. 检查 roadmap / flow / handoff 上下文，确认当前目标来自现有 task、handoff blocker、roadmap item 还是用户显式输入。
3. 委托 `skills/vibe-new/SKILL.md` 处理：
   - **Interaction Layer**：判断目标来源，提示可选 workflow
   - **Bootstrap Layer**：编排原子能力，完成 flow 注册、issue 绑定、baseline 保存
   - **Stop Conditions**：输出准备完成状态
4. 停止并提示：
   - Bootstrap 完成后，进入相应的 workflow（如 `superpowers:writing-plans`、`openspec`）
   - 恢复已有现场时提示 `/vibe-continue`

## Boundary

- workflow 只编排，不承载 handoff mode、task gate、plan 生成细则
- 不直接修改业务代码
- 不创建大命令，只组合现有原子能力
- 未经人类明确授权，不得新建物理 worktree；默认使用当前目录通过 `vibe3 flow update` 建立新的逻辑现场
