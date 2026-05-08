---
name: "vibe:new-feature"
description: Feature-oriented planning alias workflow that routes issue/roadmap-feature intake to vibe:new.
category: Workflow
tags: [workflow, vibe, planning, orchestration]
---

# vibe:new-feature

**Input**: 运行 `/vibe-new-feature <goal>`，以 feature 视角进入规划入口。

## 定位

- `vibe:new-feature` 是一个面向 feature intake 的 `alias workflow`。
- 它不是 feature 真源创建器，也不是独立的规划逻辑真源。
- 它的职责只是把用户从 “feature 视角的入口” 路由到统一的 `vibe:new` 规划路径。

## Steps

1. 回复用户：`我会先把当前目标解释为 feature 视角的规划入口，再转到统一的 vibe:new 路径。`
2. 先确认用户当前关心的是：
   - GitHub issue intake
   - feature 规划与排期
   - feature 下的 task 拆分与 plan 绑定
3. 然后统一委托 [`vibe:new`](./vibe:new.md)：
   - 由 `vibe:new` 负责后续的 roadmap / plan / task / flow 编排
   - `vibe:new-feature` 自身不再重复这些规则
4. 当 `vibe:new` 的 `plan + task binding` 完成后，本入口也随之结束。

## Boundary

- `vibe:new-feature` 是 agent workflow，不是 GitHub workflow，也不是 GitHub Project workflow。
- 它不重新定义 `GitHub issue`、`task`、`flow`。
- 它不直接承载 task binding、blocker 分类、物理 worktree 决策或 planning gates。
- 若需要新的逻辑现场，遵循 `vibe:new` 与 `CLAUDE.md` 的规则：默认在当前目录使用 `vibe3 flow update`，未经人类授权不得新建物理 worktree。
