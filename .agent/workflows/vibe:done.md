---
name: "vibe:done"
description: Skill-backed workflow that routes review-ready or post-merge closure work to the vibe-done skill.
category: Workflow
tags: [workflow, vibe, completion, archive]
---

# vibe:done

**Input**: 运行 `/vibe-done` 触发，收口当前目录承载的 flow 所对应的任务。

## 定位

- `vibe:done` 是一个 `skill-backed workflow`。
- 它用于在 PR 已 merged，或已满足 review gate、准备由 `vibe flow done` merge + closeout 时，把结算逻辑委托给 `vibe-done` skill。

## Steps

1. 回复用户：`我会先确认当前 flow / task / PR 状态，再委托 vibe-done skill 执行收口。`
2. 先读取 shell 与共享真源中的当前状态。
3. 委托 `skills/vibe-done/SKILL.md` 处理：
   - 判断是否满足收口条件
   - 更新 task / flow 相关状态
   - 输出结算结果
4. 返回收口摘要和后续建议。

## Boundary

- workflow 不承载收口判断或状态推进细节。
- 共享状态更新必须通过 skill 中调用的 shell API 完成。
