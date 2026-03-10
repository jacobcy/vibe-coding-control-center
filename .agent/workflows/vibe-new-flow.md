---
name: "Vibe: New Flow"
description: Entry point for execution flow creation
category: Workflow
tags: [workflow, vibe, planning, orchestrator]
---

# Vibe New Flow

`/vibe-new-flow` 是执行入口，不承担 `repo issue`、`GitHub Project item` / `roadmap item` 或 feature 定义职责。

它只负责两件事：

1. 创建一个新的执行现场
2. 为后续 `vibe flow bind <task-id>` 准备绑定

执行命令：

```bash
vibe flow new <slug> --branch main --save-unstash
vibe flow bind <task-id>
```

语义约束：

- `flow new <slug>` 只创建现场，不创建 feature
- `task-id` 指向 execution record
- 在选择 `task-id` 之前，必须先读取 shell 输出中的 task / roadmap 事实
- 若该 task 对应 `type=feature` 的 roadmap item，应保持 `1 feature = 1 branch = 1 PR`
- 若该 task 对应 `type=task` 的 roadmap item，则它属于更细的执行切片
