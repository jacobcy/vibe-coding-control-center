---
document_type: plan
title: GH-124 Flow Identity Audit and Closeout Plan
status: proposed
author: GPT-5 Codex
created: 2026-03-12
last_updated: 2026-03-12
related_docs:
  - docs/plans/2026-03-12-roadmap-triage-and-dependency-design.md
  - docs/plans/2026-03-12-gh-100-roadmap-dependency-view-worthiness.md
  - docs/plans/2026-03-12-roadmap-issue-triage-100-124-and-unlabeled.md
related_issues:
  - gh-124
---

# GH-124 Flow Identity Audit and Closeout Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 审计 `#124` 目前已经完成到哪一步，明确剩余最小缺口，并在不过度工程化的前提下完成其轻量收口。

**Architecture:** 先做证据式审计，不预设“还没做”或“已经做完”。按标准、skill/workflow 文案、shell help、roadmap/flow 查询输出四个面向核对 `issue -> flow` 主链是否已被部分吸收，再只补最小缺口。

**Tech Stack:** GitHub CLI, `bin/vibe`, `rg`, Markdown, Bats

---

## Goal / Non-goals

**Goal**
- 判断 `#124` 已完成、未完成、与本轮无关的部分
- 定义 `#124` 的最小完成边界
- 为后续 `#100` 轻量依赖方案提供稳定前置语义

**Non-goals**
- 不重做全部 runtime metadata
- 不做全量 UI/CLI 重排
- 不顺手把 `#100` 一起实现

## Files To Read

- `docs/standards/v2/command-standard.md`
- `docs/standards/v2/data-model-standard.md`
- `docs/standards/v2/git-workflow-standard.md`
- `.agent/workflows/vibe:start.md`
- `skills/vibe-roadmap/SKILL.md`
- `skills/vibe-start/SKILL.md`
- `skills/vibe-task/SKILL.md`
- `lib/flow.sh`
- `lib/flow_help.sh`
- `tests/flow/test_flow_lifecycle.bats`
- `tests/skills/test_skills.bats`

## Audit Output Format

审计结果必须按三类输出：

- `已完成`
- `未完成`
- `不在本轮`

且每条结论都要附证据：

- 命令输出
- grep 命中文案
- 现有测试断言
- 缺失项证据

## Minimal Done Definition for `#124`

只要满足以下四点，就可视为本轮轻量完成：

1. 文档/skill/workflow 对主链口径一致：
- 用户主视角是 `issue -> flow`
- `task` 是 execution bridge
- `roadmap item` 是 planning 中间层

2. 不再把 `task -> flow` 写成默认用户主链

3. 至少一处 shell 或展示出口不再明显与上述语义冲突

4. 明确记录本轮未覆盖内容，避免伪装成“全都做完了”

## Tasks

### Task 1: 审计 issue 语义是否已在标准和 skill 中落地

**Files:**
- Read: `docs/standards/*.md`
- Read: `skills/*.md`
- Test: `tests/skills/test_skills.bats`

**Steps**
1. 用 `rg` 检查 `issue -> flow`、`task = execution bridge`、`roadmap item = planning middle layer` 是否已存在。
2. 标出仍然写成 `task -> flow` 主链的位置。
3. 形成 `已完成 / 未完成` 清单。

**Run command**

```bash
rg -n "issue -> flow|task.*execution bridge|task -> flow|roadmap item" docs/standards skills .agent/workflows tests/skills
```

**Expected Result**

- 能明确哪些文案已经对齐，哪些还没对齐

### Task 2: 审计 shell/help/query 输出是否仍以 task 为第一锚点

**Files:**
- Read: `lib/flow.sh`
- Read: `lib/flow_help.sh`
- Test: `tests/flow/test_flow_lifecycle.bats`

**Steps**
1. 检查 `flow status/show/help` 是否仍明显以 task/runtime 为第一主语。
2. 判断这是否阻断 `#124` 的轻量完成。
3. 只保留最小必改项，不把“理想体验”都塞进本轮。

**Run command**

```bash
rg -n "current task|issue|flow status|flow show|flow bind" lib/flow.sh lib/flow_help.sh tests/flow
```

**Expected Result**

- 能界定最小缺口，而不是泛泛地说“还要重构很多”

### Task 3: 写出 `#124` 最小补齐清单

**Files:**
- Modify: 本 plan 文档

**Steps**
1. 把审计结果转成 2-4 个最小补齐动作。
2. 每个动作写清：
- 改什么
- 不改什么
- 验证命令
3. 明确哪些内容留给后续 issue，不在本轮处理。

**Run command**

```bash
true
```

**Expected Result**

- 得到一份可以执行的最小补齐清单

### Task 4: 复核 `#124` 与 `#100` 的边界

**Files:**
- Read: GitHub issue `#100`
- Read: GitHub issue `#124`

**Steps**
1. 明确 `#124` 完成后，`#100` 哪些部分可以继续。
2. 明确 `#100` 仍不得触碰的范围：
- 自动调度
- DAG
- 全量 flow gate 设计

**Run command**

```bash
gh issue view 100 --repo jacobcy/vibe-coding-control-center --json number,title,body,state,url
gh issue view 124 --repo jacobcy/vibe-coding-control-center --json number,title,body,state,url
```

**Expected Result**

- `#100` 与 `#124` 的边界不再混淆

## Expected Result

- 形成一份以证据为基础的 `#124` 审计结论
- 明确 `#124` 还剩哪些最小缺口
- 让 `#100` 后续只消费稳定语义，而不是继续耦合到未收敛主链

## Change Summary Estimate

- Modified files: 0-4
- Approx line changes: 审计后再定
- 说明：本计划先审计，再决定是否需要代码或文档修改
