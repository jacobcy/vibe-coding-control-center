---
name: "vibe:new-flow"
description: Standalone orchestration workflow for creating a new logical execution flow from the current worktree.
category: Workflow
tags: [workflow, vibe, planning, orchestration]
---

# vibe:new-flow

## 定位

- `vibe:new-flow` 是一个 `standalone orchestration workflow`。
- 它不需要同名 skill；它只负责把用户带到“新建逻辑 flow”这一步。
- 它不承担 `repo issue`、`roadmap item` 或 feature 定义职责。

## Steps

1. 回复用户：`我会把当前请求解释为新建逻辑 flow 的入口，并使用现有 shell 命令完成现场创建。`
2. 先确认当前目标是：
   - 创建新的逻辑执行现场
   - 为后续 `vibe flow bind <task-id>` 或 task 承载做准备
3. 使用现有 shell 路径：

```bash
vibe flow new <slug> --branch origin/main --save-unstash
vibe flow bind <task-id>
```

## Boundary

- `flow new <slug>` 只创建现场，不创建 feature
- `flow new <slug>` 默认在当前 worktree 内创建/切换 branch，不新建物理 worktree
- `task-id` 指向 execution record
- 若需要决定绑定哪个 task，应先回到 `vibe:task` 或 `vibe:new`，而不是在本入口里扩展规划逻辑
