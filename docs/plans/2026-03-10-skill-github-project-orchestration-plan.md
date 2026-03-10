---
document_type: plan
title: Skill GitHub Project Orchestration Plan
status: draft
scope: skills
author: Codex GPT-5
created: 2026-03-10
last_updated: 2026-03-10
related_docs:
  - docs/standards/skill-standard.md
  - docs/standards/command-standard.md
  - docs/standards/registry-json-standard.md
  - docs/references/github_project.md
---

# Skill GitHub Project Orchestration Plan

**Goal:** 让现有 workflow 和 skills 严格建立在新的 Shell/API 与共享真源之上，正确编排 GitHub 官方层对象和 Vibe 扩展字段，不再在入口文案里重新发明对象语义。

**Non-Goals:**
- 本计划不改共享真源 schema。
- 本计划不实现 GitHub API。
- 本计划不处理一次性数据回填。

**Tech Stack:** Markdown workflow files, `skills/*/SKILL.md`, `bin/vibe`, existing CLI JSON output

---

## Current Assessment

当前 workflow / skill 主要问题不在“完全错误”，而在“还不够结构化”：

1. `/vibe-new-feature`、`/vibe-new-flow` 已经部分纠偏，但还没把 `spec_standard` / `spec_ref` 纳入编排入口。
2. `/vibe-issue`、`vibe-roadmap` 仍偏重 issue/roadmap 关系，对 Project item 官方字段和扩展字段同步未形成固定问法。
3. `/vibe-task`、`/vibe-save`、`/vibe-check` 还没有把 execution spec 作为一等对象处理。
4. 现有 skill 说明没有统一规定何时读写 `spec_standard`、`execution_record_id`、`spec_ref`。

## Target Decision

1. workflow 只负责编排，不定义新对象。
2. skill 必须优先读取 Shell 输出，不自行脑补字段。
3. 所有与 task 创建/更新相关的 skill 都必须显式处理 `spec_standard` / `spec_ref`。
4. roadmap/issue 类 skill 必须把 GitHub 官方字段与 Vibe 扩展字段分开叙述。

## Files To Modify

- Modify: `.agent/workflows/vibe-new-feature.md`
- Modify: `.agent/workflows/vibe-new-flow.md`
- Modify: `.agent/workflows/vibe-issue.md`
- Modify: `.agent/workflows/vibe-task.md`
- Modify: `.agent/workflows/vibe-save.md`
- Modify: `.agent/workflows/vibe-check.md`
- Modify: `skills/vibe-roadmap/SKILL.md`
- Modify: `skills/vibe-issue/SKILL.md`
- Modify: `skills/vibe-task/SKILL.md`
- Modify: `skills/vibe-save/SKILL.md`
- Modify: `skills/vibe-check/SKILL.md`
- Test: `tests/test_skills.bats`
- Test: `tests/test_review_skills.bats`

## Task 1: 收紧 workflow 入口语义

**Files:**
- Modify: `.agent/workflows/vibe-new-feature.md`
- Modify: `.agent/workflows/vibe-new-flow.md`
- Modify: `.agent/workflows/vibe-issue.md`

**Step tasks:**

1. 给 `/vibe-new-feature` 增加一条固定编排要求：
   - 讨论阶段确认 roadmap item
   - 执行前确认 `spec_standard`
2. 给 `/vibe-new-flow` 增加“绑定前必须已有 task record”的硬约束，并明确 `spec_standard` 由 task 持有。
3. 给 `/vibe-issue` 增加 Project-first 同步说明，不把 issue 本身当 execution record。

**Expected Result:**
- workflow 入口在对象层级上不再模糊。

## Task 2: 让 `vibe-roadmap` / `vibe-issue` 技能读取新字段

**Files:**
- Modify: `skills/vibe-roadmap/SKILL.md`
- Modify: `skills/vibe-issue/SKILL.md`

**Step tasks:**

1. 在 `vibe-roadmap` 中新增“读取 GitHub 官方字段 + Vibe 扩展字段”的说明。
2. 明确 roadmap 调度时只决定：
   - roadmap item 规划状态
   - milestone
   - type
3. 明确 `spec_standard` 只是扩展字段，不参与规划类型定义。
4. 在 `vibe-issue` 中区分：
   - repo issue 创建
   - roadmap sync
   - execution record 创建

**Expected Result:**
- roadmap/issue skill 不再把执行规范和规划对象混在一起。

## Task 3: 让 `vibe-task` / `vibe-save` / `vibe-check` 使用 execution spec

**Files:**
- Modify: `skills/vibe-task/SKILL.md`
- Modify: `skills/vibe-save/SKILL.md`
- Modify: `skills/vibe-check/SKILL.md`
- Modify: `.agent/workflows/vibe-task.md`
- Modify: `.agent/workflows/vibe-save.md`
- Modify: `.agent/workflows/vibe-check.md`

**Step tasks:**

1. 在 `vibe-task` 中加入：
   - task overview 时展示 `spec_standard`
   - audit 时检查 `spec_standard/spec_ref` 缺失或非法值
2. 在 `vibe-save` 中明确：
   - 只能通过 `vibe task update --spec-standard/--spec-ref/--next-step` 持久化执行规范信息
3. 在 `vibe-check` 中新增一个检查维度：
   - roadmap 扩展字段与 task 扩展字段桥接是否一致

**Expected Result:**
- execution spec 成为 skill 层的一等信息，而非临时备注。

## Task 4: 为 skill 文案和最小 smoke tests 补回归

**Files:**
- Modify: `tests/test_skills.bats`
- Modify: `tests/test_review_skills.bats`

**Step tasks:**

1. 给关键 workflow/skill 文案增加 grep 级测试，锁定：
   - `task` = execution record
   - `spec_standard` 是扩展字段
   - 不能重写 GitHub 官方来源类型
2. 跑现有 skill smoke tests，确认文档更新不破坏基本命令。

**Expected Result:**
- skill/workflow 的语义边界被轻量回归测试锁住。

## Test Command

```bash
bats tests/test_skills.bats
bats tests/test_review_skills.bats
rg -n "spec_standard|execution_record_id|GitHub 官方字段|execution record" \
  .agent/workflows/vibe-new-feature.md \
  .agent/workflows/vibe-new-flow.md \
  .agent/workflows/vibe-issue.md \
  .agent/workflows/vibe-task.md \
  .agent/workflows/vibe-save.md \
  .agent/workflows/vibe-check.md \
  skills/vibe-roadmap/SKILL.md \
  skills/vibe-issue/SKILL.md \
  skills/vibe-task/SKILL.md \
  skills/vibe-save/SKILL.md \
  skills/vibe-check/SKILL.md
```

## Expected Result

- workflow/skill 对 GitHub 官方层和 Vibe 扩展层的口径一致。
- 入口编排会显式处理 `spec_standard` / `spec_ref`。
- skill 不再自行重定义对象模型。

## Estimated Change Summary

- Modified: 13 files
- Added: ~140-240 lines
- Removed: ~20-60 lines
- Risk: 中等
- Main risk:
  - 仅改文案不改 CLI 输出时，容易再次出现“skill 说得对，命令做不到”
  - smoke test 目前偏轻，可能无法覆盖所有 workflow 语义回退
