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
last_updated: 2026-03-08
related_docs:
  - SOUL.md
  - CLAUDE.md
  - docs/standards/command-standard.md
  - docs/standards/skill-standard.md
---

# Shell Capability Design

本文档定义 Vibe Shell 的设计原则。它不定义具体命令名，而定义命令应该如何被设计、如何被审查。

## 1. Design Goal

Vibe Shell 的唯一职责是作为 capability layer：

- 隔离 skill 与共享状态真源
- 暴露稳定、原子、可组合的方法
- 让 agent 能通过命令完成工作，而不是直接碰底层数据

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
- 单一现场动作
- 确定性检查结果

Shell Layer 不提供：

- 任务拆分决策
- 多步业务流程编排
- 优先级判断
- 版本路线图语义推理

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

- [command-standard.md](/Users/jacobcy/src/vibe-center/wt-claude-refactor/docs/standards/command-standard.md)
- [data-model-standard.md](/Users/jacobcy/src/vibe-center/wt-claude-refactor/docs/standards/data-model-standard.md)
- [registry-json-standard.md](/Users/jacobcy/src/vibe-center/wt-claude-refactor/docs/standards/registry-json-standard.md)
- [roadmap-json-standard.md](/Users/jacobcy/src/vibe-center/wt-claude-refactor/docs/standards/roadmap-json-standard.md)

设计层只回答：

- Shell 是否误解了这些语义
- Shell 是否跨层混用了这些语义
- Shell 是否提供了足够原子能力让 skill 正确使用这些语义

## 3. Atomic Method Rule

每个 Shell 命令应尽量只表达一个能力。

好例子：

- `task add`
- `task update --issue-ref ...`
- `task update --roadmap-item ...`
- `flow new`
- `flow bind`

坏例子：

- `flow new` 自动创建 task、绑定 task、推断优先级
- `task add` 自动决定 roadmap 归属
- `roadmap classify` 顺带新增 roadmap item

## 4. Hidden Workflow Ban

Shell 命令禁止隐藏工作流。

以下都属于违规：

- 隐式创建第二个实体
- 一个命令跨越两个命令域
- 默认执行本应由 skill 判断的下一步
- 用“聪明默认”替代显式编排

允许：

- 纯语法级默认值
- 对当前上下文的确定性读取
- 明确声明的单步副作用

不允许：

- 业务层推断
- 任务语义猜测
- 规划层到执行层的隐式跳转

## 5. Source Isolation Rule

skill 不得直接写共享状态真源文件。

skill 只能通过 Shell API：

- 查询共享状态
- 更新共享状态
- 创建和绑定现场

如果 skill 为了完成工作不得不直写 JSON，说明 Shell 能力缺失。

这类问题应被归类为：

- `Capability Gap`

而不是让 skill 绕过 Shell。

## 6. Review Checklist

设计或审查一个 Shell 命令时，必须逐项回答：

1. 这个命令是不是单一原子动作？
2. 这个命令是否执行了应由 skill 决定的业务逻辑？
3. 这个命令是否隐藏了额外副作用？
4. 这个命令是否让 skill 无需直接碰数据源？
5. 如果去掉 skill，这个命令是否仍在替用户做决策？

如果第 2、3、5 项中任一项答案为“是”，则该命令设计不合格。

## 7. Capability Sufficiency Test

判断 Shell 是否设计正确，不看它“聪不聪明”，只看两件事：

1. 是否提供了足够的方法让 skill 完成业务流程
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
