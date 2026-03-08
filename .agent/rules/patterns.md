# Engineering Patterns (Supplement)

本文件定义执行模式、报告模式和渐进披露模式。

术语以 [docs/standards/glossary.md](../../docs/standards/glossary.md) 为准，动作词以 [docs/standards/action-verbs.md](../../docs/standards/action-verbs.md) 为准。

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

## Progressive Disclosure
- 入口文件只保留导航、最小硬规则和引用链。
- 复杂概念、执行细则、模式约束下沉到 `rules/` 或 `docs/standards/`。
- 发现入口文件开始承载细节时，应回收至更合适的真源文档。

## Source Of Truth Usage
- 名词语义冲突时，优先查 `glossary.md`。
- 动词语义冲突时，优先查 `action-verbs.md`。
- 命令具体行为冲突时，优先查 `command-standard.md`。
- 文档规则冲突时，优先查 `docs/standards/*`，不要在入口文件临时发明解释。

## Execution Discipline
- 调度与编排属于 Skill 层或执行代理，不属于 Shell 能力层。
- 执行动作前先明确是在做 `add`、`new`、`bind`、`check` 还是 `done`，避免把动词混用成隐式流程。
- 如果一个动作词开始暗含多步业务逻辑，应拆回命令标准或 workflow 设计，而不是继续口头约定。
