---
document_type: standard
title: Shell Capability Design
status: approved
scope: shell-boundary
authority:
  - shell-responsibility
  - shell-capability-review
author: Codex GPT-5
created: 2026-03-08
last_updated: 2026-03-10
related_docs:
  - SOUL.md
  - CLAUDE.md
  - docs/standards/glossary.md
  - docs/standards/command-standard.md
  - docs/standards/skill-standard.md
---

# Shell Capability Design

本文档定义 Vibe Shell 的设计原则。它不定义具体命令名，而定义命令应该如何被设计、如何被审查。

## 1. Design Goal

Vibe Shell 的核心职责是作为 capability layer：

- 隔离 skill 与共享状态真源
- 暴露稳定、可组合、围绕共享真源的能力
- 让 agent 能通过命令完成工作，而不是直接碰底层数据

这里的“能力”不等于“只能做单字段读写”。

Shell 可以在单个命令内调用 `git`、`gh` 或其他底层工具，只要这些动作仍然服务于以下目标：

- 读取共享真源所需的确定性现场事实
- 将共享真源对应的现场动作落地
- 同步当前单一现场与共享真源之间的一致事实

Shell 不是：

- workflow engine
- orchestrator
- scheduler
- 业务决策器

## 2. Three-Layer Contract

### 2.1 Data Layer

共享状态真源只包括：

- `roadmap.json`
- `registry.json`
- `worktrees.json`

Data Layer 只保存共享事实，不暴露给 skill 直接手工读写。

### 2.2 Shell Layer

Shell Layer 提供：

- 原子读操作
- 原子写操作
- 围绕共享真源的中等粒度现场动作
- 确定性检查结果

Shell Layer 可以：

- 为了完成共享真源相关操作，顺带执行必要的 `git` / `gh` / worktree 动作
- 在单一命令里同步一个共享事实所需的一组确定性副作用
- 基于显式参数与当前单一现场，完成无需业务判断的机械步骤

Shell Layer 不提供：

- 任务拆分决策
- 多步业务流程编排
- 优先级判断
- 版本路线图语义推理

### 2.2.1 What Shell Must Not Decide

“Shell 不做逻辑判断”的准确含义是：

- 不替 skill 决定该拆几个 task
- 不替 skill 决定 task 该关联哪个 issue / roadmap item
- 不替 skill 决定是否应该开启下一个 flow
- 不替 skill 决定剩余改动属于当前交付目标还是下一个交付目标
- 不替 skill 决定 `next_step`、优先级、归属和执行顺序

只要这些判断仍需依赖上层语义理解，责任就在 skill，而不在 Shell。

### 2.3 Skill Layer

Skill Layer 负责：

- 理解用户目标
- 决定拆几个 task
- 决定关联哪个 roadmap item / issue
- 决定是否开新 flow
- 决定一个 flow 承载一个还是多个 task

一句话：

- Shell 提供工具
- Skill 使用工具完成业务逻辑

### 2.4 Semantic Dependency

当 Shell 设计涉及 `roadmap`、`task`、`flow` 的业务语义时，必须引用以下真源，而不是在设计文档中重复定义：

- [glossary.md](/Users/jacobcy/src/vibe-center/wt-claude-refactor/docs/standards/glossary.md)
- [command-standard.md](/Users/jacobcy/src/vibe-center/wt-claude-refactor/docs/standards/command-standard.md)
- [data-model-standard.md](/Users/jacobcy/src/vibe-center/wt-claude-refactor/docs/standards/data-model-standard.md)
- [registry-json-standard.md](/Users/jacobcy/src/vibe-center/wt-claude-refactor/docs/standards/registry-json-standard.md)
- [roadmap-json-standard.md](/Users/jacobcy/src/vibe-center/wt-claude-refactor/docs/standards/roadmap-json-standard.md)

设计层只回答：

- Shell 是否误解了这些语义
- Shell 是否跨层混用了这些语义
- Shell 是否提供了足够原子能力让 skill 正确使用这些语义

## 3. Atomic Method Rule

每个 Shell 命令应尽量只表达一个清晰的能力边界。

这里不要求 Shell 退化成“只读一个字段”或“只写一个字段”。只要一组动作服务于同一个共享事实或同一个单一现场同步目标，就仍然可以视为一个能力。

好例子：

- `task add`
- `task update --issue-ref ...`
- `task update --roadmap-item ...`
- `flow new`
- `flow bind`

坏例子：

- `flow new` 自动创建 task、决定 flow 对应 task、推断优先级
- `task add` 自动决定 roadmap 归属
- `roadmap classify` 顺带新增 roadmap item

## 4. Hidden Workflow Ban

Shell 命令禁止隐藏工作流。

以下都属于违规：

- 隐式创建第二个实体
- 一个命令跨越两个命令域
- 默认执行本应由 skill 判断的下一步
- 用“聪明默认”替代显式编排
- 用命令内部推断替代 skill 的业务归属判断

允许：

- 纯语法级默认值
- 对当前上下文的确定性读取
- 明确声明的单步副作用
- 为同步共享真源而执行的一组确定性 `git` / `gh` / worktree 副作用

不允许：

- 业务层推断
- 任务语义猜测
- 规划层到执行层的隐式跳转
- 把“机械落地”偷换成“业务判断”

## 5. Source Isolation Rule

skill 不得直接写共享状态真源文件。

skill 只能通过 Shell API：

- 查询共享状态
- 更新共享状态
- 创建、绑定和同步与共享真源相关的现场

如果 skill 为了完成工作不得不直写 JSON，说明 Shell 能力缺失。

这类问题应被归类为：

- `Capability Gap`

而不是让 skill 绕过 Shell。

## 6. Review Checklist

设计或审查一个 Shell 命令时，必须逐项回答：

1. 这个命令是不是单一原子动作？
2. 这个命令是否替 skill 决定了归属、拆分、优先级、下一步等业务逻辑？
3. 这个命令是否隐藏了额外副作用？
4. 这个命令是否让 skill 无需直接碰数据源？
5. 如果去掉 skill，这个命令是否仍在替用户做语义决策，而不只是执行机械步骤？

如果第 2、3、5 项中任一项答案为“是”，则该命令设计不合格。

## 7. Capability Sufficiency Test

判断 Shell 是否设计正确，不看它“聪不聪明”，只看两件事：

1. 是否提供了足够的方法让 skill 完成业务流程，而不必自己拼接高 token 成本的机械步骤
2. 是否没有越权执行本应由 skill 负责的编排逻辑

也就是说：

- 能力不足 = 需要补命令
- 越权编排 = 需要拆命令

## 8. Application To Future Shell Work

后续所有 Shell 设计文件都必须显式回答：

- 本次新增的原子能力是什么
- 它服务哪个 skill 编排场景
- 它是否引入了隐藏 workflow
- 它是否让 skill 更少碰共享状态，而不是更多

如果一份 Shell 设计文件没有回答这些问题，则设计未完成。
