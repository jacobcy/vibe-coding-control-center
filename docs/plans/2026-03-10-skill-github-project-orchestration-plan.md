---
document_type: plan
title: Skill GitHub Project Orchestration Plan
status: draft
scope: skills
author: Codex GPT-5
created: 2026-03-10
last_updated: 2026-03-10
related_docs:
  - docs/references/github_project.md
  - docs/standards/skill-standard.md
  - docs/standards/command-standard.md
  - docs/standards/data-model-standard.md
---

# Skill GitHub Project Orchestration Plan

**Goal:** 重写 workflow 和 skills 的实施方案，使其严格依赖当前 shell/API 与共享真源，不再用项目内部旧术语覆盖 GitHub Project 官方语义。

**Non-Goals:**
- 本计划不修改 shared-state schema。
- 本计划不实现 GitHub API。
- 本计划不替代 shell contract 改造。

**Tech Stack:** Markdown workflow files, `skills/*/SKILL.md`, `bin/vibe`, JSON output contracts, Bats smoke tests

---

## Current Assessment

最近的语义纠偏已经修正了标准层和部分文案，所以这里的重点不再是“全面纠错”，而是把编排层剩余缺口收口。旧方案过时的地方主要在于它仍假设 workflow/skill 需要自己定义对象模型，而当前标准已经明确：

1. workflow 和 skill 只能编排，不得重定义对象层级。
2. `roadmap item` 是 GitHub Project item mirror。
3. `task` 是 execution record。
4. `spec_standard/spec_ref` 是扩展桥接字段，不是 GitHub 官方身份。
5. skill 必须优先读取 shell 输出，而不是从文案推导隐含字段。

## Target Decision

1. workflow 层只表达顺序与前置条件，不发明新对象。
2. skill 层只消费 shell 输出中的官方字段与扩展字段，不自行拼接身份。
3. 所有与 task 相关的编排都显式处理 `spec_standard/spec_ref`。
4. 所有与 roadmap/issue 相关的编排都显式区分：
   - repo issue
   - roadmap item
   - task
   - flow

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
- Modify: `tests/skills/test_skills.bats`
- Modify: `tests/skills/test_review_skills.bats`

## Task 1: 收紧 workflow 的对象边界

**Files:**
- Modify: `.agent/workflows/vibe-new-feature.md`
- Modify: `.agent/workflows/vibe-new-flow.md`
- Modify: `.agent/workflows/vibe-issue.md`
- Modify: `.agent/workflows/vibe-task.md`

**Step tasks:**

1. 在 workflow 中固定对象链：
   - repo issue -> roadmap item -> task -> flow -> PR
2. 明确 `vibe-new-flow` 只接受已有 task，不生成规划对象。
3. 明确 `vibe-issue` 只处理 issue/roadmap 关系，不把 issue 说成 execution record。
4. 明确 `vibe-task` 负责 execution record，而不是 roadmap type。

**Expected Result:**
- workflow 不再把 GitHub Project 规划语义和本地执行语义混用。

## Task 2: 让 roadmap/issue skill 明确使用官方层与扩展层

**Files:**
- Modify: `skills/vibe-roadmap/SKILL.md`
- Modify: `skills/vibe-issue/SKILL.md`

**Step tasks:**

1. 明确 roadmap 读取的是 GitHub Project item mirror。
2. 明确 skill 只把 `spec_standard/spec_ref` 当扩展桥接字段描述。
3. 明确 roadmap/issue skill 不得决定 execution record 身份。
4. 明确 GitHub 官方来源类型不得被 `openspec/kiro/superpowers/supervisor` 覆盖。

**Expected Result:**
- roadmap/issue skill 对 GitHub 官方语义的叙述与标准一致。

## Task 3: 让 task/save/check skill 以 execution spec 为一等输入

**Files:**
- Modify: `skills/vibe-task/SKILL.md`
- Modify: `skills/vibe-save/SKILL.md`
- Modify: `skills/vibe-check/SKILL.md`
- Modify: `.agent/workflows/vibe-save.md`
- Modify: `.agent/workflows/vibe-check.md`

**Step tasks:**

1. `vibe-task` 明确展示和审计 `spec_standard/spec_ref`。
2. `vibe-save` 明确持久化执行规范信息必须经过 `vibe task update`。
3. `vibe-check` 增加桥接一致性检查：
   - roadmap item 的 `execution_record_id`
   - task 的 `spec_standard/spec_ref`
4. 所有 skill 说明都强调“先读 shell 输出，再做编排”。

**Expected Result:**
- execution spec 成为编排层的稳定输入，而不是散落在自由文案中的约定。

## Task 4: 为 skill/workflow 增加语义 smoke tests

**Files:**
- Modify: `tests/skills/test_skills.bats`
- Modify: `tests/skills/test_review_skills.bats`

**Step tasks:**

1. 对关键 workflow/skill 文案做 grep 级断言，锁定：
   - `task = execution record`
   - `roadmap item = GitHub Project item mirror`
   - `spec_standard/spec_ref` 是扩展字段
2. 锁定禁用表述：
   - 把 `type=task` 写成本地 task
   - 把 `openspec/kiro/superpowers/supervisor` 写成 GitHub 官方来源类型
3. 保持测试轻量，只验证编排语义不回退。

**Expected Result:**
- skill/workflow 语义边界可以通过轻量测试持续检查。

## Test Command

```bash
bats tests/skills/test_skills.bats
bats tests/skills/test_review_skills.bats
rg -n "execution record|GitHub Project item mirror|spec_standard|spec_ref|type=task" \
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

- skill/workflow 只做编排，不再生造 GitHub Project 之外的对象身份。
- shell、shared-state、skill 三层可以围绕同一对象模型协作。

## Estimated Change Summary

- Modified: 13 files
- Added/Changed Lines: ~150-260 lines
- Risk: 中等
- Main risk:
  - 若 shell 输出仍未补齐，skill 文案会出现“语义正确但命令做不到”的断层
  - smoke test 过轻时，可能遗漏局部 workflow 的旧术语回流
