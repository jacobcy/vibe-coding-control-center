# Skill Loop Semantic Realignment Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将新确认的 skill 语义收敛为标准，并据此修正 `vibe-new / vibe-start / vibe-task / vibe-check` 及相关 workflow / memo，使 skill loop 从旧链切换到新链而不再自相矛盾。

**Architecture:** 先把“哪条链是主链、哪两个 skill 是审计旁路”写成稳定标准，再以标准去压实 memo、workflow、skill 文案与测试。实现顺序固定为“标准 -> memo -> workflow/skills -> tests”，避免边改 skill 边改标准导致二次漂移。

**Tech Stack:** Markdown standards, workflow docs, `skills/*/SKILL.md`, Bats doc-regression tests

---

## Goal

- 明确主链应为：
  - `vibe-issue`
  - `vibe-roadmap`
  - `vibe-new`
  - `vibe-start`
  - spec execution (`openspec` / `superpowers` / 其他 `spec_standard`)
  - `vibe-commit`
  - `vibe-integrate`
  - `vibe-done`
- 明确旁路应为：
  - `vibe-task`
  - `vibe-check`

## Non-Goals

- 本计划不修改 shell 命令实现。
- 本计划不改变 OpenSpec / Superpowers 的执行细则。
- 本计划不重做 `vibe-commit -> vibe-integrate -> vibe-done` 已落地的 review gate。
- 本计划不处理历史 handoff 数据修复。

## Current Decision To Encode

1. `vibe-issue` 只负责 issue 创建、补全、查重、修正，不负责 roadmap 排期，不负责 task 创建。
2. `vibe-roadmap` 只负责 roadmap 调度、triage、版本排布与“下一个 roadmap 做什么”。
3. `vibe-new` 是旧链到新链的转换器：
   - 发生在旧 flow 语义里
   - 不创建 task
   - 不进入执行
   - 只决定下一个主 issue、是否带未提交改动进入新 flow、还是清空工作区再进新 flow
4. `vibe-start` 发生在进入新 flow 之后：
   - 从 issue 落 task / 需求声明
   - 再交给对应 `spec_standard` 的执行体系
   - 不再承担旧 flow 到新 flow 的转换职责
5. `vibe-task` 是 task-centered audit：
   - 核查 `issue <-> roadmap item <-> task <-> flow` 关系
   - 负责 task registry / roadmap-task mapping / task 数据质量
6. `vibe-check` 是 runtime / recovery audit：
   - 核查 `task <-> flow <-> worktree` 现场一致性
   - 负责 stale binding / runtime recovery
   - 不是项目级 roadmap / task registry 总审计

## Files To Modify

- Modify: `docs/standards/skill-standard.md`
- Modify: `docs/standards/skill-trigger-standard.md`
- Modify: `docs/standards/git-workflow-standard.md`
- Modify: `.agent/workflows/vibe:new.md`
- Modify: `.agent/workflows/vibe:start.md`
- Modify: `.agent/workflows/vibe:task.md`
- Modify: `.agent/workflows/vibe:check.md`
- Modify: `skills/vibe-issue/SKILL.md`
- Modify: `skills/vibe-roadmap/SKILL.md`
- Modify: `skills/vibe-new/SKILL.md`
- Modify: `skills/vibe-start/SKILL.md`
- Modify: `skills/vibe-task/SKILL.md`
- Modify: `skills/vibe-check/SKILL.md`
- Modify: `docs/references/skill-loop-memo.md`
- Modify: `tests/skills/test_skills.bats`

## Step Tasks

### Task 1: Freeze the new source-of-truth semantics

**Files:**
- Modify: `docs/standards/skill-standard.md`
- Modify: `docs/standards/skill-trigger-standard.md`
- Modify: `docs/standards/git-workflow-standard.md`

**Steps:**
1. Write failing doc-regression test for the new `vibe-new / vibe-start / vibe-task / vibe-check` boundaries.
2. Run the test and confirm it fails on old wording.
3. Update standards so the new chain is stated once, with cross-references rather than duplicated prose.
4. Re-run the doc-regression test and confirm it passes.
5. Commit.

### Task 2: Align the human memo with the new chain

**Files:**
- Modify: `docs/references/skill-loop-memo.md`
- Test: `tests/skills/test_skills.bats`

**Steps:**
1. Update the memo so it matches the new semantics exactly.
2. Ensure the memo clearly distinguishes main chain vs audit sidecars.
3. Add or refine test expectations that grep the memo for the new chain wording.
4. Run the memo-related test and confirm it passes.
5. Commit.

### Task 3: Thin workflows to the corrected entry semantics

**Files:**
- Modify: `.agent/workflows/vibe:new.md`
- Modify: `.agent/workflows/vibe:start.md`
- Modify: `.agent/workflows/vibe:task.md`
- Modify: `.agent/workflows/vibe:check.md`
- Test: `tests/skills/test_skills.bats`

**Steps:**
1. Update `vibe:new` workflow so it only frames old-flow to new-flow conversion and stops before task creation.
2. Update `vibe:start` workflow so it frames “enter new flow -> derive task from issue -> hand off to spec execution”.
3. Update `vibe:task` workflow so it stays task-centered and does not drift into runtime recovery.
4. Update `vibe:check` workflow so it stays runtime/recovery-centered and does not claim whole-chain audit ownership.
5. Run the workflow-related test and confirm it passes.
6. Commit.

### Task 4: Align skill docs to the corrected responsibility split

**Files:**
- Modify: `skills/vibe-issue/SKILL.md`
- Modify: `skills/vibe-roadmap/SKILL.md`
- Modify: `skills/vibe-new/SKILL.md`
- Modify: `skills/vibe-start/SKILL.md`
- Modify: `skills/vibe-task/SKILL.md`
- Modify: `skills/vibe-check/SKILL.md`
- Test: `tests/skills/test_skills.bats`

**Steps:**
1. Update `vibe-issue` to remove any wording that implies roadmap placement or task creation.
2. Update `vibe-roadmap` to reinforce “dispatch brain only”.
3. Update `vibe-new` to describe old-chain to new-chain conversion without task creation.
4. Update `vibe-start` to describe new-flow entry, issue-to-task derivation, and handoff into `spec_standard`.
5. Update `vibe-task` to state task-centered chain audit and explicitly separate it from runtime recovery.
6. Update `vibe-check` to state runtime/recovery audit and explicitly separate it from task-centered chain audit.
7. Run the skill-doc test suite and confirm it passes.
8. Commit.

### Task 5: Full regression and gap review

**Files:**
- Test: `tests/skills/test_skills.bats`
- Review: all files touched above

**Steps:**
1. Run the full skill-doc test command.
2. Re-read the main chain and confirm there is no remaining contradiction between standards, memo, workflows, and skills.
3. If contradictions remain, fix them in the authoritative file first, then repair references.
4. Commit the final reconciliation change if needed.

## Test Command

```bash
bats tests/skills/test_skills.bats
```

## Expected Result

- `vibe-new` no longer claims task creation inside the old flow.
- `vibe-start` becomes the new-flow entry that derives task from issue and then hands off into execution specs.
- `vibe-task` and `vibe-check` are clearly split into task-centered audit vs runtime/recovery audit.
- standards, memo, workflows, and skill docs all describe the same chain.
- `tests/skills/test_skills.bats` passes with the new wording locked in.

## Change Summary

- Modified: 14-15 files
- Added: 0 files if reusing the existing memo, otherwise 1 file if the memo is relocated
- Approximate lines: 180-320
