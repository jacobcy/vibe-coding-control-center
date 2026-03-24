---
document_type: plan
title: commit preflight metadata plan
status: proposed
scope: commit-preflight-metadata
author: Codex GPT-5
created: 2026-03-11
last_updated: 2026-03-11
related_docs:
  - skills/vibe-commit/SKILL.md
  - .agent/workflows/vibe:commit.md
  - docs/standards/v3/command-standard.md
  - docs/standards/v3/git-workflow-standard.md
  - docs/standards/v3/handoff-governance-standard.md
  - docs/standards/glossary.md
  - lib/task_actions.sh
  - lib/task_write.sh
  - lib/flow_show.sh
  - tests/flow/test_flow_bind_done.bats
---

# Commit Preflight Metadata Plan

**Goal:** 在 `vibe-commit` 编排层增加最小元数据完整性 preflight，使提交前能发现当前 flow/task 的关键登记缺口。

**Non-Goals:**
- 本计划不新增 `bin/vibe commit` shell 子命令。
- 本计划不一次性规范化全部历史 task 的 `spec_ref` / `spec_standard`。
- 本计划不替代 `vibe task audit` 的周期性清账职责。
- 本计划不修改 roadmap sync、GitHub Project 合同或历史补链主逻辑。

**Tech Stack:** Markdown workflow docs, skill docs, Zsh shell helpers, Bats tests, shared state JSON (`registry.json` / `worktrees.json`)

---

## Current Decision

本轮讨论已形成以下最小规则：

1. `vibe-commit` 前必须检查当前 flow 是否存在 `current_task`。
2. `current_task` 必须能在共享真源中解析，并与当前 runtime branch 对齐。
3. 第一版只做“最小守门”：
   - `hard block`
     - 当前 flow 无 `current_task`
     - 当前 task 未绑定当前 runtime branch
   - `warning`
     - 当前 task 缺 `issue_refs`
     - 当前 task 缺 `roadmap_item_ids`
     - 当前 task 缺 `spec_standard/spec_ref`
4. `task 应当有 plan/spec` 是治理方向，但第一版不把缺 plan 直接提升为硬阻断，避免历史遗留任务一次性全部卡死。
5. 该逻辑属于 skill/workflow 编排层，不进入新的 shell 原子命令。

## Files To Modify

- Modify: `.agent/workflows/vibe:commit.md`
- Modify: `skills/vibe-commit/SKILL.md`
- Modify: `tests/skills/test_skills.bats`

## Task 1: 收敛 preflight 规则到 workflow

**Files:**
- Modify: `.agent/workflows/vibe:commit.md`

**Step tasks:**

1. 在 `Review Gate` 之后、工作区分类之前加入元数据 preflight 步骤。
2. 明确 workflow 必须先读取：
   - `vibe flow show --json`
   - 必要时 `vibe task show <task-id> --json`
3. 定义第一版 `hard block` 条件：
   - `current_task` 为空
   - task 不存在
   - task 的 `runtime_branch` 与当前 flow branch 不一致或为空
4. 定义第一版 `warning` 条件：
   - 缺 `issue_refs`
   - 缺 `roadmap_item_ids`
   - 缺 `spec_standard/spec_ref`

**Expected Result:**
- `vibe-commit` workflow 在真正分类和提交前就会暴露最小登记缺口。

## Task 2: 收敛 preflight 规则到 skill 文案

**Files:**
- Modify: `skills/vibe-commit/SKILL.md`

**Step tasks:**

1. 在读取 `vibe flow show --json` 后补一段显式 preflight。
2. 用项目术语明确边界：
   - `task` 是 execution record
   - `issue_refs` / `roadmap_item_ids` / `spec_*` 是提交前的审计辅助元数据
3. 明确 `hard block` 与 `warning` 的动作差异：
   - `hard block`：停止提交，先补最小登记
   - `warning`：允许继续，但必须向用户报告风险
4. 保持 skill 不直接修改 GitHub Project 或 issue 结构。

**Expected Result:**
- skill 文案与 workflow 一致，不会把“缺 plan/spec”误写成第一版硬阻断。

## Task 3: 增加文本级回归测试

**Files:**
- Modify: `tests/skills/test_skills.bats`

**Step tasks:**

1. 为 `vibe-commit` 新增文本断言，覆盖：
   - 提交前必须读取 `vibe flow show --json`
   - 必须检查当前 flow/task 最小元数据完整性
   - `hard block` 与 `warning` 的边界文案存在
2. 防止后续 skill 回退为“只做 git diff 分类，不看 task/flow 元数据”。

**Expected Result:**
- skill/workflow 的 preflight 语言可被轻量测试锁定。

## Test Command

```bash
rg -n "preflight|current_task|runtime branch|issue_refs|roadmap_item_ids|spec_standard|spec_ref|hard block|warning" \
  .agent/workflows/vibe:commit.md \
  skills/vibe-commit/SKILL.md

bats tests/skills/test_skills.bats
```

## Expected Result

- `vibe-commit` 在提交前具备最小元数据守门。
- 第一版不会因为历史缺 `spec_ref` 而全面阻断提交。
- `hard block` 与 `warning` 的边界对用户和后续 agent 都清晰可见。

## Estimated Change Summary

- Modified: 3 files
- Added: 0 files
- Added/Changed Lines: ~40-90 lines
- Main risks:
  - 若把缺 `spec_ref` 直接做成硬阻断，会一次性卡住大量历史任务。
  - 若只改 skill 不改 workflow，编排入口仍可能绕过 preflight。
  - 若无测试，后续容易回退为只看 git 状态、不看执行元数据。
