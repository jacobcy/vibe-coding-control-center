---
document_type: plan
title: Handoff Governance Standard Plan
status: draft
scope: handoff-governance
author: Codex GPT-5
created: 2026-03-11
last_updated: 2026-03-11
related_docs:
  - AGENTS.md
  - CLAUDE.md
  - docs/standards/git-workflow-standard.md
  - skills/vibe-save/SKILL.md
  - skills/vibe-continue/SKILL.md
  - skills/vibe-commit/SKILL.md
  - skills/vibe-integrate/SKILL.md
  - skills/vibe-done/SKILL.md
---

# Handoff Governance Standard Plan

**Goal:** 建立独立的 handoff 标准文件，并把“读取后必须核查、发现不一致有修正义务”的规则上提到根入口文档，使 handoff 不再主要依赖 skill 内部约定。

**Non-Goals:**
- 本计划不引入新的共享状态真源或本地缓存层。
- 本计划不修改 shell 命令语义或 `.git/vibe/*.json` schema。
- 本计划不重写全部 workflow，只收口 handoff 治理规则与高风险 skill 引述。

**Tech Stack:** Markdown standards, root entry docs, `skills/*/SKILL.md`, `rg`-based smoke verification

---

## Current Decision

本轮讨论已形成以下决策：

1. `.agent/context/task.md` 是本地 handoff，不是真源。
2. handoff 规则不应主要散落在 skill 中，而应上提为项目级标准。
3. `AGENTS.md` 与 `CLAUDE.md` 需要显式告诉所有 agent：
   - handoff 只作补充线索
   - 读取 handoff 后必须核查共享真源与 git 现场
   - 若发现 handoff 与现场不一致，有修正义务，不能放着不改
4. skill 仍可保留 handoff 段落，但应改成简要引述标准，而不是各自发明规则。

## Files To Modify

- Create: `docs/standards/handoff-governance-standard.md`
- Modify: `AGENTS.md`
- Modify: `CLAUDE.md`
- Modify: `skills/vibe-save/SKILL.md`
- Modify: `skills/vibe-continue/SKILL.md`
- Modify: `skills/vibe-commit/SKILL.md`
- Modify: `skills/vibe-integrate/SKILL.md`
- Modify: `skills/vibe-done/SKILL.md`

## Task 1: 新增 handoff 标准文件

**Files:**
- Create: `docs/standards/handoff-governance-standard.md`

**Step tasks:**

1. 定义 handoff 的角色边界：
   - `.agent/context/task.md` 是本地交接记录
   - 不是真源
   - 不得替代共享状态或 git 现场
2. 定义读取规则：
   - 先核查共享真源与现场
   - 再读取 handoff 作为补充
3. 定义维护义务：
   - 读取了 handoff 且发现不一致，必须修正或明确降级为 stale
   - 完成阶段切换的 skill 退出前必须更新 handoff
4. 定义禁止项：
   - 不得把 handoff 当 cached facts
   - 不得读取后继续沿用过时结论

**Expected Result:**
- handoff 治理拥有单独标准真源，后续文档与 skill 不再各写一套。

## Task 2: 在入口文档中上提 handoff 规则

**Files:**
- Modify: `AGENTS.md`
- Modify: `CLAUDE.md`

**Step tasks:**

1. 在 `AGENTS.md` 中加入 handoff 入口规则，面向所有 agent 说明：
   - `task.md` 默认只是本地 handoff
   - 不是真源
   - 看过后若与现场不一致，必须修正
2. 在 `CLAUDE.md` 中加入简要硬规则或上下文管理规则：
   - handoff 只作补充
   - 不允许基于旧 handoff 直接做判断
3. 两处都只做高层规则，不复制标准全文，改为引用 `docs/standards/handoff-governance-standard.md`

**Expected Result:**
- 不依赖是否进入某个具体 skill，agent 一进入项目就能看到 handoff 边界。

## Task 3: 收口高风险 skill 的 handoff 语义

**Files:**
- Modify: `skills/vibe-save/SKILL.md`
- Modify: `skills/vibe-continue/SKILL.md`
- Modify: `skills/vibe-commit/SKILL.md`
- Modify: `skills/vibe-integrate/SKILL.md`
- Modify: `skills/vibe-done/SKILL.md`

**Step tasks:**

1. 把 skill 中重复的 handoff 定义改成短引用：
   - 指向 `docs/standards/handoff-governance-standard.md`
2. 在读取 handoff 的 skill 中统一加入一句硬规则：
   - 若 handoff 与当前真源或现场不一致，必须修正后再退出
3. 在会改变阶段事实的 skill 中保留“退出前更新 handoff”的要求，但不再重复长篇定义
4. 保证 skill 文案不再把 handoff 描述成可直接驱动决策的来源

**Expected Result:**
- skill 只执行标准，不再各自承载 handoff 宪法。

## Task 4: 增加轻量文档级验证

**Files:**
- Modify: `tests/skills/test_skills.bats`

**Step tasks:**

1. 为 handoff 标准与关键 skill 文案增加 `rg`/grep 级断言：
   - `task.md` 是 handoff，不是真源
   - 读取后发现不一致必须修正
   - skill 通过引用标准而不是自造规则
2. 锁定根入口文档中存在 handoff 边界说明

**Expected Result:**
- 以后 handoff 治理语言若回退，可以被轻量测试及时发现。

## Test Command

```bash
rg -n "handoff|task\\.md|真源|修正义务" \
  docs/standards/handoff-governance-standard.md \
  AGENTS.md \
  CLAUDE.md \
  skills/vibe-save/SKILL.md \
  skills/vibe-continue/SKILL.md \
  skills/vibe-commit/SKILL.md \
  skills/vibe-integrate/SKILL.md \
  skills/vibe-done/SKILL.md

bats tests/skills/test_skills.bats
```

## Expected Result

- handoff 规则有独立标准真源。
- 所有 agent 从入口文档就能知道 handoff 不是事实真源。
- 关键 skill 读取 handoff 后具备核查与修正义务，而不是只做提醒。

## Estimated Change Summary

- Modified: 8 files
- Added: 1 file
- Added/Changed Lines: ~120-200 lines
- Main risk:
  - 若只改 root docs 而不改 skill，旧 skill 仍会保留分散表述
  - 若只改 skill 不加测试，后续容易回退为各写各的 handoff 规则
