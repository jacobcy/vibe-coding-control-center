---
name: "vibe:new"
description: Planning-entry workflow that routes intake to the vibe-new skill and stops after plan/task binding is ready.
category: Workflow
tags: [workflow, vibe, planning, orchestration]
---

# vibe:new

**Input**: 运行 `/vibe-new <goal-or-slug> [--save-unstash]`，进入规划入口。

## 职责

处理旧 flow 到新 flow 的转换，准备人机协作环境。不创建 task，不进入执行。

## Steps

1. 回复用户：`进入规划模式。我会先确认目标来源，再委托 vibe-new skill 完成 intake、plan 和 task 绑定。`
2. 检查 roadmap / flow / handoff 上下文，确认当前目标来自现有 task、handoff blocker、roadmap item 还是用户显式输入。
3. 委托 `skills/vibe-new/SKILL.md` 处理业务判断：
   - 选择 intake 来源
   - 必要时联动 `vibe-issue`、`vibe-roadmap`、`writing-plans`
   - 决定主 issue 与新 flow 入口形态
   - 判断是否携带未提交改动进入新 flow
4. 旧 flow 到新 flow 的转换确定后，停止并提示用户改用 `/vibe-start` 从 issue 落 task。

## Boundary

- workflow 只编排，不承载 handoff mode、task gate、plan 生成细则
- 不直接修改业务代码
- 未经人类明确授权，不得新建物理 worktree；默认使用当前目录里的 `vibe flow new` 建立新的逻辑现场
