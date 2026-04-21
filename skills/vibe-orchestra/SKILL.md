---
name: vibe-orchestra
description: Use when the user wants heartbeat-style governance over the issue pool. inspect running issues, judge which issue is worth starting next, backfill assignee-triggered candidates, and propose non-state label or routing actions. Do not use for single-flow execution governance, coding, or implementation work.
---

# Vibe Orchestra

> 项目命令参考见 `skills/vibe-instruction/SKILL.md`

`vibe-orchestra` 负责 orchestra 心跳层的 **assignee issue pool** 治理。它关心的范围仅限于 assignee issue pool：现在有哪些 issue 正在运行、哪些已满足 assignee 触发条件但尚未进入调度，以及在人机协作环节接下来哪个 assignee issue 值得优先处理。它不负责单 flow 执行，也不负责 broader repo backlog 的 triage。

## 概念区别

- **governance**：无临时 worktree 的 scan agent，只观察和建议，不执行代码修改。
- **supervisor/apply**：有临时 worktree 的治理执行 agent，负责实际治理执行动作。
- **`supervisor/governance/assignee-pool.md`（原 orchestra.md）**：governance supervisor material，是 governance agent 的角色材料，不是 runtime orchestra 本体。
- **runtime orchestra / governance supervisor material / supervisor apply 是三个独立概念，不可混淆。**

优先级判断口径必须对齐 `supervisor/governance/assignee-pool.md`。可以把 `vibe-orchestra` 视为自动治理 supervisor 在人机协作环节的落地判断器：它不发明另一套优先级规则，只读取当前现场并按 supervisor 已定义的排序模型，指导人类如何找到下一个需要处理的 issue。

术语、对象边界与触发分流以以下标准为准：

- `docs/standards/glossary.md`
- `docs/standards/action-verbs.md`
- `docs/standards/v3/skill-standard.md`
- `docs/standards/v3/command-standard.md`
- `docs/standards/v3/python-capability-design.md`
- `docs/standards/v3/worktree-lifecycle-standard.md`
- `docs/standards/v3/skill-trigger-standard.md`

## Scope

`vibe-orchestra` 只回答两类问题，且均以 **assignee issue pool** 为前提：

- assignee issue pool 中现在有哪些 issue 正在运行
- 在当前现场下，assignee issue pool 中接下来哪个 issue 值得建议优先处理

这里的“建议 issue”只是参考，不是强制调度结果；最终仍需结合 flow / PR / 人类当前上下文判断。

补充说明：

- assignee 是启动事实源
- `state/*` label 只反映 flow 实际状态，不是主触发源
- 常驻 server 与定时巡检只是运行模式差异，不改变本 skill 的职责边界
- 自动 ready queue 的建议顺序按 `milestone -> roadmap/* -> priority/[0-9] -> issue number` 理解，仅作用于 assignee issue pool 内部
- 人机协作时，若某个 assignee issue 已被人类明确接手、已有活跃 PR、或当前上下文要求先收口 follow-up，可临时覆盖自动顺序，但必须说明理由
- **不处理 supervisor issue，也不对 broader repo backlog 做 triage**

## What It Reads

以下观察面均以 **assignee issue pool** 为范围：

- running issues（assignee issue pool 中正在运行的 issue）
- assignee issue pool 中尚未启动但可被考虑的候选 issues
- `uv run python src/vibe3/cli.py task status` 中 assignee issue 的 active / ready / blocked 现场与 ready queue rank
- 当前是否已有人工明确接手的 assignee issue / PR follow-up / review 收口上下文
- assignee 与 queue / flow 现场事实
- assignee issue pool 中 issue 的 state labels
- dependency information such as blocked_by
- orchestra heartbeat status 与相关文档
- `supervisor/governance/assignee-pool.md` 中的 queue guidance 与治理边界

## What It Produces

- running issues summary
- backfill candidates summary
- next-issue recommendation
- ready queue ordering judgment
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
- 不负责替代人类做最终业务优先级拍板；它只给出基于 supervisor 语义和当前现场的建议

当请求跨出这些边界时，按 `docs/standards/v3/skill-trigger-standard.md` 分流，不在本 skill 中重写职责矩阵。

## Execution Pattern

1. 查看当前 assignee issue pool 中的 running issues 与 queue / flow 现场
2. 补捞 assignee issue pool 中已满足 assignee 条件但尚未进入调度的候选 issue
3. 判断 assignee issue pool 中是否已经存在足够明确的执行现场
4. 参考 `supervisor/governance/assignee-pool.md`，按 `milestone -> roadmap/* -> priority/[0-9] -> issue number` 对 assignee issue pool 的自动 ready queue 做人机治理判断
5. 结合当前人工上下文，识别 assignee issue pool 中哪些 issue 虽然不在自动顺位最前，但更适合现在先处理
6. 如有必要，提出最小 non-state label 调整建议（仅作用于 assignee issue pool 内）
7. 在治理结论处停止

## Output Contract

输出至少包含：

- `Running issues`
- `Backfill candidates`
- `Next issue`
- `Why this one now`
- `Label actions`
- `Why`

如果当前没有合适的建议 issue，明确写无，并说明原因。

## Stop Point

完成治理建议后停止。
不要进入执行分配、实现方案、代码修改或单 flow 管理。
