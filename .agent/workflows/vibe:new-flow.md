---
name: "vibe:new-flow"
description: Standalone orchestration workflow for creating a new logical execution flow from the current worktree.
category: Workflow
tags: [workflow, vibe, planning, orchestration]
---

# vibe:new-flow

## 定位

- `vibe:new-flow` 是一个 `standalone orchestration workflow`。
- 它不需要同名 skill；它只负责把用户带到"新建逻辑 flow"这一步。
- 它不承担 `GitHub issue` 或 feature 定义职责。

## Steps

1. 回复用户：`我会把当前请求解释为新建逻辑 flow 的入口，并使用现有 shell 命令完成现场创建。`
2. 先确认当前目标是：
   - 创建新的逻辑执行现场
   - 为后续 `vibe3 flow bind <issue-number>` 或 task 承载做准备
3. 使用现有 shell 路径：

```bash
git checkout -b dev/issue-<N>
vibe3 flow update
vibe3 flow bind <N>
```

## Boundary

- `git checkout -b` 创建新分支，`vibe3 flow update` 注册该分支为 flow
- Flow 创建在当前 worktree 内，不新建物理 worktree
- `<N>` 是 issue number，用于绑定 flow 与 issue
- 若需要决定绑定哪个 issue，应先回到 `vibe:task` 或 `vibe:new`，而不是在本入口里扩展规划逻辑