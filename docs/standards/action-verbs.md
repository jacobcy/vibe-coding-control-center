---
document_type: standard
title: Action Verbs Standard
status: approved
scope: action-language
authority:
  - action-verb-meanings
  - action-verb-reminders
author: Codex GPT-5
created: 2026-03-08
last_updated: 2026-03-08
related_docs:
  - SOUL.md
  - CLAUDE.md
  - docs/README.md
  - docs/standards/glossary.md
  - docs/standards/command-standard.md
---

# 高频动作词标准

本文档是 Vibe Center 高频动作词的唯一真源。

本文档只提供默认含义、执行提醒和禁止隐含项，用于减少语义歧义，不扩展成功能设计、命令设计、skill 设计或 workflow 设计。

名词术语见 [glossary.md](/Users/jacobcy/src/vibe-center/wt-claude-refactor/docs/standards/glossary.md)。

## 1. Use Rule

- 这些动作词只提供默认解释与执行提醒
- 若具体命令语义与本表冲突，以 [command-standard.md](/Users/jacobcy/src/vibe-center/wt-claude-refactor/docs/standards/command-standard.md) 为准
- 若出现新的高频动作词歧义，应优先补本文档，而不是在入口文档中临时解释

## 2. Action Verbs

### 2.1 `add`

- 默认含义：向共享模型新增一个实体
- 前置提醒：确认新增的是稳定记录，而不是临时现场
- 不要隐含什么：不要自动创建额外实体，不要自动推进下一步流程

### 2.2 `list`

- 默认含义：列出某一类对象的集合视图
- 前置提醒：确认输出对象范围和过滤条件
- 不要隐含什么：不要隐式修改状态，不要把 `list` 做成审计或修复动作

### 2.3 `show`

- 默认含义：展示单个对象的详情
- 前置提醒：确认对象标识唯一且存在
- 不要隐含什么：不要顺带更新对象，不要顺带执行绑定或同步

### 2.4 `update`

- 默认含义：更新已有对象的显式字段
- 前置提醒：确认更新目标已存在，且修改字段在该层职责内
- 不要隐含什么：不要借 `update` 隐式创建对象，不要跨层补写无关状态

### 2.5 `remove`

- 默认含义：移除已有对象或解除已有绑定
- 前置提醒：确认移除动作不会误删仍在使用的共享事实
- 不要隐含什么：不要把 `remove` 扩展成清理整段 workflow

### 2.6 `close issue`

- 默认含义：关闭对应的 GitHub Issue
- 前置提醒：检查与该 issue 相关的 task 是否已完成，或已明确说明未完成原因
- 不要隐含什么：不自动关闭 task，不自动归档，不自动迁移数据

### 2.7 `new`

- 默认含义：创建一个新的运行时现场
- 前置提醒：确认这是新现场，而不是向共享模型新增实体
- 反歧义提醒：对 `vibe flow new` 而言，默认是在当前 worktree 中切入新的 flow / branch 现场，不等于新建物理 worktree
- 不要隐含什么：不要自动建 task，不要自动决定 roadmap 归属，不要自动提 PR

### 2.8 `bind`

- 默认含义：建立已有对象之间的明确绑定关系
- 前置提醒：确认两端对象都已存在，且绑定关系符合标准
- 不要隐含什么：不要借 `bind` 创建对象，不要隐式修改第三方状态

### 2.9 `sync`

- 默认含义：将外部事实或外部状态同步到当前系统
- 前置提醒：确认同步来源和覆盖边界
- 不要隐含什么：不要把 `sync` 扩展成业务决策或批量修复

### 2.10 `review`

- 默认含义：执行审查、检查或评估
- 前置提醒：确认 review 只产出结论、反馈或状态，不直接写业务真源
- 不要隐含什么：不要把 `review` 做成发布、合并或修复动作

### 2.11 `pr`

- 默认含义：面向 GitHub Pull Request 的发布动作
- 前置提醒：确认当前 flow/branch 是可发布的，且不属于通用探索 flow
- 不要隐含什么：不要把 `pr` 当作 task 创建、task 完成或 flow 收尾的代名词

### 2.12 `done`

- 默认含义：完成当前收尾动作或结束当前现场
- 前置提醒：确认对应的发布、合并或结算动作已经满足前置条件
- 不要隐含什么：不要把 `done` 理解成“自动处理所有后续状态”

### 2.13 `check`

- 默认含义：执行检查、验证或审计
- 前置提醒：确认检查对象、失败条件和输出格式明确
- 不要隐含什么：不要把 `check` 做成修复命令，不要在失败时静默改数据
