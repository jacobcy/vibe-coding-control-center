---
document_type: plan
title: GH-157 Semantic Cleanup Prerequisite Plan
status: proposed
author: GPT-5 Codex
created: 2026-03-13
last_updated: 2026-03-13
related_docs:
  - docs/plans/2026-03-13-gh-157-remote-first-roadmap-governance-design.md
  - docs/plans/2026-03-13-gh-157-remote-first-roadmap-governance-plan.md
  - docs/standards/glossary.md
  - docs/standards/v2/data-model-standard.md
  - docs/standards/v2/command-standard.md
  - docs/standards/v2/registry-json-standard.md
related_issues:
  - gh-157
  - gh-158
  - gh-152
---

# GH-157 Semantic Cleanup Prerequisite Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在执行 remote-first roadmap governance 之前，先冻结仓库核心对象语义，消除 `worktree/flow/branch` 与 `repo issue/task issue` 的混用，并为 `worktrees.json` 清退建立明确前置条件。

**Architecture:** 先做文档与标准层的语义冻结，再做 `worktrees.json` 的残留审计与清退计划，最后才恢复 GH-157 主计划。`roadmap.json` 暂时保留，但只按 projection / cache / backup 描述，不再暗示 execution gate 或长期关系真源地位。

**Tech Stack:** Markdown, Zsh, jq, ripgrep

---

## Goal / Non-goals

**Goal**
- 把 `worktree`、`branch`、`flow`、`task`、`repo issue`、`task issue` 的正式语义一次冻结
- 解决标准层对 `worktrees.json` 身份定位不一致的问题
- 为后续 `worktrees.json` 清退提供可执行边界，而不是边做边猜
- 明确 `roadmap.json` 当前只保留为 cache / projection / backup

**Non-goals**
- 本计划不直接修改 shell 实现
- 本计划不立即删除 `worktrees.json`
- 本计划不引入新的长期本地 issue registry
- 本计划不把 `task issue` 直接落成新的持久化实体类型

## Preconditions

- 当前 git worktree 必须干净，再开始文档冻结与后续清退设计
- GH-157 主计划暂缓进入实现 phase，先完成本前置计划
- 如发现现有标准与实现冲突，以仓库真源和可验证行为为准，不凭历史口口相传修文案

## Decision Baseline

### 1. `worktree`

- 只表示 Git 物理目录
- 不是 flow
- 不是 branch
- 不再承担 execution 身份锚点

### 2. `flow`

- 是对 branch 的逻辑交付现场包装
- 对用户表达“当前正在推进的交付切片”
- branch 是开放 flow 的身份锚点
- worktree 只是承载 flow 的容器，不是 flow 本体

### 3. `task issue`

- 不是新的 GitHub 对象类型
- 不是与 `repo issue` 平行的新实体
- 它只是某个 `repo issue` 在 execution 语义中承担 task 主闭环锚点时的角色称呼
- 若一个 task 对应多个 `issue_refs`，后续标准需要明确哪个是主闭环 issue

### 4. `roadmap.json`

- 当前保留
- 只按 mirror / cache / projection / backup 描述
- 不再作为 execution gate 真源
- 是否长期保留，留待后续实现与运行证据决定

## Task 1: 冻结术语边界

**Files:**
- Modify: `docs/standards/glossary.md`
- Modify: `docs/standards/v2/data-model-standard.md`
- Modify: `docs/standards/v2/command-standard.md`
- Modify: `docs/standards/v2/registry-json-standard.md`

**Step 1: 对齐 `worktree / branch / flow`**

- 把 `worktree` 固定为物理目录
- 把 `flow` 固定为 branch 的逻辑现场包装
- 删除或修正文档里把 `worktrees.json` 写成现场真源的表述

**Step 2: 对齐 `repo issue / task issue`**

- 在 glossary 中新增 `task issue` 术语
- 明确它是 `repo issue` 的 execution role，而不是平行新实体
- 在 registry / command 标准里补“task 必须能表达主闭环 issue”这一语义缺口

**Step 3: 对齐 `roadmap.json` 口径**

- 统一写成 mirror / cache / projection / backup
- 删除把 roadmap 暗示为 execution hard gate 的表述

**Step 4: 验证**

Run:

```bash
rg -n "worktrees.json|现场态真源|task issue|issue_refs|execution gate|projection|cache" docs/standards
```

Expected:
- 标准层不再同时出现“`worktrees.json` 是现场真源”和“flow 已解耦 `worktrees.json`”这类冲突口径

## Task 2: 产出 `worktrees.json` 清退计划

**Files:**
- Read: `lib/flow_runtime.sh`
- Read: `lib/task_query.sh`
- Read: `lib/check_groups.sh`
- Read: `tests/flow/*.bats`
- Read: `tests/task/*.bats`
- Create: `docs/plans/2026-03-13-gh-157-worktrees-json-retirement-plan.md`

**Step 1: 盘点残留依赖**

- 列出哪些命令仍直接读取或写入 `worktrees.json`
- 区分“当前必要兼容层”和“可以直接移除的历史残留”

**Step 2: 定义清退边界**

- 哪些 runtime 事实改由现场直接读取
- 哪些历史事实只保留在 `flow-history.json`
- 哪些校验从 `worktrees.json` 迁移为 branch / registry / git 现场联合判断

**Step 3: 定义兼容期策略**

- 在清退完成前，把 `worktrees.json` 定位成 compatibility cache / audit hint
- 禁止继续向它增加新的主模型职责

**Step 4: 验证**

Run:

```bash
rg -n "worktrees\\.json" lib tests docs/standards docs/plans
```

Expected:
- 能得到一份带优先级的残留依赖清单，供后续独立实施

## Task 3: 回写 GH-157 总方案前置条件

**Files:**
- Modify: `docs/plans/2026-03-13-gh-157-remote-first-roadmap-governance-design.md`
- Modify: `docs/plans/2026-03-13-gh-157-remote-first-roadmap-governance-plan.md`

**Step 1: 前移前置条件**

- 明确“语义清理 -> `worktrees.json` 清退 -> GH-157 主计划”这一顺序

**Step 2: 加入提醒**

- `roadmap.json` 当前只按 cache / projection 解释
- `task issue` 是推荐显式强调的 execution role
- 若不先冻结语义，remote-first 实施容易继续走样

**Step 3: 验证**

Run:

```bash
rg -n "precondition|task issue|worktrees.json|cache|projection" docs/plans/2026-03-13-gh-157-remote-first-roadmap-governance-*.md docs/plans/2026-03-13-gh-157-semantic-cleanup-prerequisite-plan.md
```

Expected:
- 总方案与前置计划的顺序、术语与风险提醒一致

## Exit Criteria

- 标准层对象边界冻结完成
- `task issue` 是否显式进入正式语义已有明确决定
- `worktrees.json` 清退计划已独立成文
- GH-157 主计划已改为依赖本前置计划，而不是直接进入实现 phase
