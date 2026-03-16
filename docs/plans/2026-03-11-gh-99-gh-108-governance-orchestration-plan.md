---
document_type: plan
title: gh-99 gh-108 governance orchestration
status: proposed
scope: current-flow-gh-96-backlog-cleanup
author: Codex GPT-5
created: 2026-03-11
last_updated: 2026-03-11
related_issues:
  - gh-96
  - gh-99
  - gh-108
related_docs:
  - docs/standards/git-workflow-standard.md
  - docs/standards/v2/handoff-governance-standard.md
  - skills/vibe-done/SKILL.md
  - skills/vibe-integrate/SKILL.md
  - skills/vibe-issue/SKILL.md
  - skills/vibe-roadmap/SKILL.md
  - tests/skills/test_skills.bats
---

# GH-99 + GH-108 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在当前 `gh-96-backlog-cleanup` flow 中，为已绑定的 `gh-99` 与 `gh-108` 补齐一套最小治理实现：明确 merged PR 后 plan 终态规则，并在 skill 编排层定义主 issue / sub-issue 的追加边界。

**Architecture:** 本次只改标准文档与 skill 编排文案，不改 `vibe` shell 命令，不引入新的共享状态字段。`gh-99` 的规则落在 workflow 标准与 post-merge handoff 边界；`gh-108` 的规则落在 `vibe-issue` / `vibe-roadmap` 的编排判断，要求先定义主 issue 范围，再判断新问题应追加为 sub-issue 还是新建主 issue。

**Tech Stack:** Markdown standards, skill docs, Bats text-contract tests, `rg`, `bats`

---

## Current Flow Context

- 当前 flow：`gh-96-backlog-cleanup`
- 当前 task：`2026-03-11-task-pr-bridge-audit`
- 当前绑定 issue：`gh-96`、`gh-99`、`gh-108`（另含 `gh-106/107/109` 历史同流事项）
- 约束：只处理 `gh-99` + `gh-108` 相关治理规则，不顺手处理 `gh-100/#101/#102/#103`

## Non-Goals

- 不新增或修改 `bin/vibe` / `lib/*.sh` shell 能力
- 不实现 GitHub sub-issue API 调用
- 不重做 roadmap / task / flow 数据模型
- 不处理当前 worktree 中与本计划无关的 `.gitignore` 或其他未提交改动

## Execution Preconditions

- 预计实现会修改 `6` 个现有文件，并新增 `0` 个实现文件
- 因为受影响文件数 `>5`，执行模式开始前需要人类确认
- 只允许通过文档与 skill 文案建立治理边界，不得把判断下沉到 shell 层

## Task 1: 固化 `gh-99` 的 merged PR terminal 规则

**Files:**
- Modify: `docs/standards/git-workflow-standard.md`
- Modify: `docs/standards/v2/handoff-governance-standard.md`

**Step 1: 写出 failing contract 清单**

- 明确需要补入的文本断言：
  - `PR merged => 原 plan 进入 terminal state`
  - merge 后允许补记的内容仅限交付证据、审计说明、handoff 更正、follow-up 链接
  - merge 后新需求必须重新进入 `repo issue -> roadmap item -> task/flow`

**Step 2: 先写最小测试断言**

Run:

```bash
rg -n "terminal|merged PR|follow-up issue|新的 repo issue|roadmap item" tests/skills/test_skills.bats docs/standards/git-workflow-standard.md docs/standards/v2/handoff-governance-standard.md
```

Expected:

- 变更前找不到完整规则组合，或仅有零散 follow-up 语义，无法覆盖 `gh-99` 验收口径

**Step 3: 写最小标准改动**

- 在 `git-workflow-standard` 中补一段 post-merge 终态规则
- 在 `handoff-governance-standard` 中补一段“handoff 可补记，但不得把 merge 后新需求写回旧 plan”的维护义务

**Step 4: 复跑断言**

Run:

```bash
rg -n "plan.*terminal|merged PR.*terminal|follow-up.*repo issue|roadmap item" docs/standards/git-workflow-standard.md docs/standards/v2/handoff-governance-standard.md
```

Expected:

- 两个标准文件都能直接提供 `gh-99` 的规则证据

**Step 5: Commit**

```bash
git add docs/standards/git-workflow-standard.md docs/standards/v2/handoff-governance-standard.md
git commit -m "docs: define merged-pr terminal governance"
```

## Task 2: 把 `gh-99` 规则接到 post-merge skill 编排

**Files:**
- Modify: `skills/vibe-done/SKILL.md`
- Modify: `skills/vibe-integrate/SKILL.md`

**Step 1: 写 failing test 断言**

Run:

```bash
rg -n "terminal|follow-up issue|new issue|旧 plan|已 merged" skills/vibe-done/SKILL.md skills/vibe-integrate/SKILL.md tests/skills/test_skills.bats
```

Expected:

- 当前 skill 只表达 merge / close / follow-up 流程，尚未明确“旧 plan 不得继续承载新需求”

**Step 2: 写最小 skill 文案**

- `vibe-integrate`：补充“仅处理当前 PR follow-up；若 PR 已 merged 且出现新目标，转入新 intake，不得回写旧 plan”
- `vibe-done`：补充“收口阶段只能补证据与 follow-up 链接；新需求必须创建/挂接新的 repo issue”

**Step 3: 复跑断言**

Run:

```bash
rg -n "旧 plan|新需求|repo issue|terminal|follow-up" skills/vibe-done/SKILL.md skills/vibe-integrate/SKILL.md
```

Expected:

- 两个 skill 都显式引用终态规则，并把 merge 后新增需求导向新 intake

**Step 4: Commit**

```bash
git add skills/vibe-done/SKILL.md skills/vibe-integrate/SKILL.md
git commit -m "docs: wire merged-pr terminal rule into skills"
```

## Task 3: 在编排层定义主 issue / sub-issue 追加规则

**Files:**
- Modify: `skills/vibe-issue/SKILL.md`
- Modify: `skills/vibe-roadmap/SKILL.md`

**Step 1: 写 failing test 断言**

Run:

```bash
rg -n "sub-issue|主 issue|母题|scope|范围|追加" skills/vibe-issue/SKILL.md skills/vibe-roadmap/SKILL.md tests/skills/test_skills.bats
```

Expected:

- 现有文案只覆盖 intake / roadmap 分类，未定义何时继续挂靠主 issue、何时拆新主 issue

**Step 2: 写最小编排规则**

- `vibe-issue`：
  - 新增主 issue 范围最小表达要求
  - 新问题进入时先判断是否仍属于原治理母题
  - 若超界，则要求新建独立主 issue
- `vibe-roadmap`：
  - 只在规划层承接上述判断结果
  - 禁止把 parent/sub-issue 判断偷换成 roadmap item 或 shell runtime 逻辑

**Step 3: 复跑断言**

Run:

```bash
rg -n "主 issue|sub-issue|范围|超出原范围|新建独立 issue|skill/workflow" skills/vibe-issue/SKILL.md skills/vibe-roadmap/SKILL.md
```

Expected:

- 两个 skill 明确 `gh-108` 的层级边界与判断路径

**Step 4: Commit**

```bash
git add skills/vibe-issue/SKILL.md skills/vibe-roadmap/SKILL.md
git commit -m "docs: define parent issue scope orchestration"
```

## Task 4: 增加回归测试，防止治理文案回退

**Files:**
- Modify: `tests/skills/test_skills.bats`

**Step 1: 写失败中的测试用例**

- 新增 2 个 `bats` 文本契约测试：
  - `gh-99`: 标准/skill 必须同时出现 merged PR terminal 与 new intake 语义
  - `gh-108`: `vibe-issue` / `vibe-roadmap` 必须同时出现 parent issue scope / sub-issue append / out-of-scope new issue 语义

**Step 2: 先跑单测确认失败**

Run:

```bash
bats tests/skills/test_skills.bats
```

Expected:

- 新增测试在实现前失败，失败点对应缺失的关键词断言

**Step 3: 在前三个任务完成后复跑**

Run:

```bash
bats tests/skills/test_skills.bats
```

Expected:

- 全部通过
- 输出包含新增的 `ok` 用例

**Step 4: Commit**

```bash
git add tests/skills/test_skills.bats
git commit -m "test: lock governance orchestration wording"
```

## Full Verification

Run:

```bash
bats tests/skills/test_skills.bats
```

Expected:

- `0` exit code
- `gh-99` / `gh-108` 相关文本契约测试通过

补充人工验证：

1. 打开 `docs/standards/git-workflow-standard.md`，确认 merged PR 后旧 plan 只允许补证据与 follow-up 链接
2. 打开 `skills/vibe-done/SKILL.md`，确认收口阶段不会把新需求塞回旧 plan
3. 打开 `skills/vibe-issue/SKILL.md` 与 `skills/vibe-roadmap/SKILL.md`，确认主 issue / sub-issue 判断被明确留在 skill 编排层

## Expected Result

- `gh-99`：项目内形成清晰规则，merged PR 后原 plan 进入终态，后续新需求必须重新 intake
- `gh-108`：项目内形成清晰规则，主 issue / sub-issue 的范围判断只在 skill/workflow 层完成
- 至少一处自动化测试防止规则回退

## Planned Change Summary

- Modify: `docs/standards/git-workflow-standard.md`
- Modify: `docs/standards/v2/handoff-governance-standard.md`
- Modify: `skills/vibe-done/SKILL.md`
- Modify: `skills/vibe-integrate/SKILL.md`
- Modify: `skills/vibe-issue/SKILL.md`
- Modify: `skills/vibe-roadmap/SKILL.md`
- Modify: `tests/skills/test_skills.bats`
- Estimated lines added: `+45` to `+80`
- Estimated lines removed: `0` to `-10`
- Estimated lines modified: `~20` to `~40`
