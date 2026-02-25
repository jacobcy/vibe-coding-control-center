# Engineering Patterns (Supplement)

本文件定义执行模式，不重复 `SOUL.md` / `CLAUDE.md` 的治理条款。

## Context First
- 开始前先读取：`git status`、`git log`、`.agent/context/*`。
- 任何结论都需要对应证据（命令、diff、测试结果）。

## Idempotent Steps
- 设计可重复执行步骤，避免二次执行破坏状态。
- 对外部副作用操作加前置检查（例如分支、路径、文件存在性）。

## Fail Fast
- 前置条件不满足立即停止，并输出明确阻塞原因。

## Structured Reporting
- 输出固定结构：结论、证据、下一步。
