---
document_type: plan
title: gh-101 gh-105 roadmap intake gate
status: proposed
scope: issue-101-105-setup
author: Codex GPT-5
created: 2026-03-11
last_updated: 2026-03-11
related_issues:
  - gh-101
  - gh-105
related_docs:
  - skills/vibe-roadmap/SKILL.md
  - skills/vibe-issue/SKILL.md
  - docs/standards/v3/command-standard.md
  - tests/skills/test_skills.bats
---

# GH-101 + GH-105 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 为 `#101` 与 `#105` 落地最小文档与测试契约，明确 repo issue 进入 GitHub Project 的 intake gate 归属，以及 `vibe-roadmap` 只需要 intake 视图而不需要本地长期 issue 真源。

**Architecture:** 本轮只修改 skill 文案、命令标准文案与文本契约测试，不新增 shell 命令、不新增本地缓存模型。`#101` 先收敛 intake gate 的职责分层；`#105` 再收敛 intake 视图的数据来源与非目标，并分别用测试锁定文本契约。

**Tech Stack:** Zsh CLI, Markdown docs, Bats, `rg`

---

## Goal

- 明确不是所有 `repo issue` 都自动进入 GitHub Project
- 明确 intake gate 的治理判断属于 `vibe-roadmap` / `vibe-issue` skill 边界，不下沉为 shell 智能 gate
- 明确 `vibe-roadmap` 消费的是 repo issue intake 视图，而不是本地长期 issue registry

## Non-Goals

- 不新增 `vibe roadmap` shell 子命令
- 不新增本地 repo issue registry 或 snapshot schema
- 不实现 GitHub Project 字段同步或依赖字段写回
- 不修改 `lib/`、`bin/`、`scripts/` 的运行时代码

## Tech Stack

- 文档与 skill：Markdown
- 契约验证：`tests/skills/test_skills.bats`
- 文本扫描：`rg`

## Files To Modify

- `skills/vibe-roadmap/SKILL.md`
- `skills/vibe-issue/SKILL.md`
- `docs/standards/v3/command-standard.md`
- `tests/skills/test_skills.bats`

## Verification Command

```bash
bats tests/skills/test_skills.bats
```

## Expected Result

- `vibe-roadmap` 明确承担 intake gate 的规划判断
- `vibe-issue` 明确只负责候选 issue intake，不负责自动纳入 Project
- `command-standard` 明确 `roadmap sync` 只同步规划层 mirror，不引入本地 repo issue 真源
- `tests/skills/test_skills.bats` 新增文本契约并通过

## Commit Plan

1. `docs: define roadmap intake gate responsibilities`
2. `docs: define issue intake view without local cache`

## Task 1: Implement `#101` intake gate boundary

**Files:**
- Modify: `skills/vibe-roadmap/SKILL.md`
- Modify: `skills/vibe-issue/SKILL.md`
- Modify: `docs/standards/v3/command-standard.md`
- Modify: `tests/skills/test_skills.bats`

**Step 1: Write the failing contract test for intake gate ownership**

- 在 `tests/skills/test_skills.bats` 新增一个测试，使用 `rg` 断言以下语义存在：
  - `不是所有 repo issue 都自动进入 Project`
  - `vibe-roadmap` 承担 intake gate / triage 判断
  - `vibe-issue` 创建 issue 时只打候选标签或保持候选资格，不自动进入 Project
  - shell 层不做智能 gate

**Step 2: Run the focused test and confirm it fails**

Run:

```bash
bats tests/skills/test_skills.bats --filter "intake gate"
```

Expected:

- 新测试失败
- 失败原因是目标文本尚未出现在对应文档中，而不是测试语法错误

**Step 3: Update `skills/vibe-roadmap/SKILL.md`**

- 增补 intake gate 文案：
  - 只有经过 roadmap triage 的候选 `repo issue` 才能进入 GitHub Project
  - `vibe-roadmap` 负责纳入 / 不纳入 / 待讨论判断
  - 规划判断必须先读 shell 输出，再做语义决策
  - shell 不负责自动决定 issue 是否进 Project

**Step 4: Update `skills/vibe-issue/SKILL.md`**

- 增补候选资格文案：
  - `vibe-issue` 创建 issue 时附加 `vibe-task` 只表示候选资格
  - 候选 issue 不等于自动进入 GitHub Project
  - 进入 Project 需要后续 `vibe-roadmap` triage

**Step 5: Update `docs/standards/v3/command-standard.md`**

- 在 `vibe roadmap` 相关章节补充边界说明：
  - `roadmap sync` 不对全部 repo issue 做自动 intake
  - shell 不负责智能 intake gate
  - repo issue 是否纳入 roadmap item，由上层 skill/workflow 判断

**Step 6: Run the focused test and confirm it passes**

Run:

```bash
bats tests/skills/test_skills.bats --filter "intake gate"
```

Expected:

- 该测试通过

**Step 7: Run the full verification suite**

Run:

```bash
bats tests/skills/test_skills.bats
```

Expected:

- 全部通过

**Step 8: Commit Task 1**

Run:

```bash
git add skills/vibe-roadmap/SKILL.md skills/vibe-issue/SKILL.md docs/standards/v3/command-standard.md tests/skills/test_skills.bats
git commit -m "docs: define roadmap intake gate responsibilities"
```

Expected:

- 形成只覆盖 `#101` 语义边界的一次提交

## Task 2: Implement `#105` intake view without local long-term cache

**Files:**
- Modify: `skills/vibe-roadmap/SKILL.md`
- Modify: `docs/standards/v3/command-standard.md`
- Modify: `tests/skills/test_skills.bats`

**Step 1: Write the failing contract test for intake view semantics**

- 在 `tests/skills/test_skills.bats` 新增一个测试，使用 `rg` 断言以下语义存在：
  - `repo issue intake 视图`
  - 运行时查询 + roadmap mirror 对比
  - 不新增本地长期 repo issue 真源 / registry / cache
  - 若未来需要留痕，应优先是 triage 决策或审计快照，而不是 issue 整池真源

**Step 2: Run the focused test and confirm it fails**

Run:

```bash
bats tests/skills/test_skills.bats --filter "intake view"
```

Expected:

- 新测试失败
- 失败原因是缺失目标文案，而不是 Bats 语法问题

**Step 3: Update `skills/vibe-roadmap/SKILL.md`**

- 增补 intake 视图文案：
  - `vibe-roadmap` 使用 repo issue intake 视图进行 triage
  - intake 视图来自运行时查询与 roadmap mirror 对比
  - 不维护本地长期 issue cache / registry
  - 若需要审计，保存的是 triage 决策快照而不是整池 issue 真源

**Step 4: Update `docs/standards/v3/command-standard.md`**

- 在 `vibe roadmap` 相关标准中补充：
  - `roadmap sync` 只同步 GitHub Project mirror
  - repo issue 仍以 GitHub 为真源
  - 规划层允许消费 intake view，但不建立新的 repo issue 持久化模型

**Step 5: Run the focused test and confirm it passes**

Run:

```bash
bats tests/skills/test_skills.bats --filter "intake view"
```

Expected:

- 该测试通过

**Step 6: Run the full verification suite**

Run:

```bash
bats tests/skills/test_skills.bats
```

Expected:

- 全部通过

**Step 7: Commit Task 2**

Run:

```bash
git add skills/vibe-roadmap/SKILL.md docs/standards/v3/command-standard.md tests/skills/test_skills.bats
git commit -m "docs: define issue intake view without local cache"
```

Expected:

- 形成只覆盖 `#105` 语义边界的一次提交

## Change Summary Estimate

- `skills/vibe-roadmap/SKILL.md`: modify, about 15-25 lines
- `skills/vibe-issue/SKILL.md`: modify, about 6-12 lines
- `docs/standards/v3/command-standard.md`: modify, about 10-18 lines
- `tests/skills/test_skills.bats`: modify, about 20-35 lines

Total estimate:

- added: 35-60 lines
- modified: 20-35 lines
- removed: 0-10 lines
