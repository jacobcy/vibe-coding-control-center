---
name: vibe-orchestra
description: Use when the user wants heartbeat-style governance over the issue pool: inspect running issues, judge which issue is worth starting next, backfill assignee-triggered candidates, and propose non-state label or routing actions. Do not use for single-flow execution governance, coding, or implementation work.
---

# Vibe Orchestra

> 项目命令参考见 `skills/vibe-instruction/SKILL.md`

`vibe-orchestra` 负责 orchestra 心跳层的 issue pool 治理。它关心的是现在有哪些 issue 正在运行、哪些已满足 assignee 触发条件但尚未进入调度，以及接下来哪个 issue 值得建议启动。它不负责单 flow 执行。

术语、对象边界与触发分流以以下标准为准：
- `docs/standards/glossary.md`
- `docs/standards/action-verbs.md`
- `docs/standards/v3/skill-standard.md`
- `docs/standards/v3/command-standard.md`
- `docs/standards/v3/python-capability-design.md`
- `docs/standards/v3/worktree-lifecycle-standard.md`
- `docs/standards/v3/skill-trigger-standard.md`

## Scope

`vibe-orchestra` 只回答两类问题：
- 现在有哪些 issue 正在运行
- 接下来哪个 issue 值得建议启动

这里的“建议 issue”只是参考，不是强制调度结果；最终仍需结合 flow / worktree / PR 现场判断。

补充说明：

- assignee 是启动事实源
- `state/*` label 只反映 flow 实际状态，不是主触发源
- 常驻 server 与定时巡检只是运行模式差异，不改变本 skill 的职责边界

## What It Reads

- running issues
- 尚未启动但可被考虑的候选 issues
- assignee 与 queue / flow 现场事实
- issue state labels
- dependency information such as blocked_by
- orchestra heartbeat status 与相关文档

## What It Produces

- running issues summary
- backfill candidates summary
- suggested issues list
- 最小 non-state label actions 或 routing suggestions
- start / wait / defer recommendations with short reasons

## Hard Boundary

- 不负责 task registry 或 task 数据质量审计
- 不负责 runtime 绑定修复
- 不负责 roadmap 规划或版本目标
- 不负责 GitHub issue intake、模板补全或查重
- 不负责单个 flow 的 plan / run / review
- 不负责决定单个 issue 一定要先 plan、run、review 还是直接人工操作
- 不负责把 `state/*` label 当作启动执行的主驱动
- 不负责写代码

当请求跨出这些边界时，按 `docs/standards/v3/skill-trigger-standard.md` 分流，不在本 skill 中重写职责矩阵。

## Execution Pattern

1. 查看当前 running issues 与 queue / flow 现场
2. 补捞已满足 assignee 条件但尚未进入调度的候选 issue
3. 判断是否已经存在足够明确的执行现场
4. 对未运行 issue 给出建议顺序
5. 如有必要，提出最小 non-state label 调整建议
6. 在治理结论处停止

## Output Contract

输出至少包含：
- `Running issues`
- `Backfill candidates`
- `Suggested issues`
- `Label actions`
- `Why`

如果当前没有合适的建议 issue，明确写无，并说明原因。

## Stop Point

完成治理建议后停止。
不要进入执行分配、实现方案、代码修改或单 flow 管理。
