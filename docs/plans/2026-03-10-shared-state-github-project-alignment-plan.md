---
document_type: plan
title: Shared State GitHub Project Alignment Plan
status: draft
scope: shared-state
author: Codex GPT-5
created: 2026-03-10
last_updated: 2026-03-10
related_docs:
  - docs/references/github_project.md
  - docs/standards/data-model-standard.md
  - docs/standards/roadmap-json-standard.md
  - docs/standards/registry-json-standard.md
---

# Shared State GitHub Project Alignment Plan

**Goal:** 让本地共享真源真正落地“GitHub 官方字段 + Vibe 扩展字段”的双层模型，使 `roadmap.json`、`registry.json`、`worktrees.json` 在实现层与当前标准保持一致。

**Non-Goals:**
- 本计划不实现 GitHub API 同步。
- 本计划不改 workflow 或 skill 文案。
- 本计划不覆盖历史 bootstrap/cutover。

**Tech Stack:** Zsh, jq, `.git/vibe/*.json`, Bats, shell helper functions

---

## Current Assessment

标准层已经纠正为 GitHub Project 兼容语义，但共享真源实现层大概率仍停留在旧 schema 假设。当前要解决的是实现落地，不是再定义新术语：

1. `roadmap.json` 应承载 mirrored GitHub Project item 的官方锚点和本地桥接字段。
2. `registry.json` 应承载 execution record 的扩展字段，但不能复制 GitHub item 身份。
3. `worktrees.json` 应继续只描述 runtime 现场，不被规划层字段污染。
4. 旧方案引用了仓库里并不存在的 `tests/test_roadmap.bats`，需要改成当前可维护的测试拆分。

## Target Decision

1. `roadmap.json` item 至少稳定承载：
   - `github_project_item_id`
   - `content_type`
   - `execution_record_id`
   - `spec_standard`
   - `spec_ref`
2. `registry.json` task 至少稳定承载：
   - `spec_standard`
   - `spec_ref`
   - 不得承载 `github_project_item_id`
   - 不得承载 `content_type`
3. `worktrees.json` 不新增 GitHub Project 身份字段。
4. 以 JSON 输出契约和 Bats fixture 锁定这些边界。

## Files To Modify

- Modify: `lib/roadmap_write.sh`
- Modify: `lib/roadmap_query.sh`
- Modify: `lib/task_actions.sh`
- Modify: `lib/task_write.sh`
- Modify: `lib/task_query.sh`
- Modify: `tests/task/test_task_ops.bats`
- Modify: `tests/task/test_task_sync.bats`
- Modify: `tests/task/test_task_helper.zsh`
- Create: `tests/contracts/test_shared_state_contracts.bats`

## Task 1: 补齐 roadmap item 写入契约

**Files:**
- Modify: `lib/roadmap_write.sh`
- Create: `tests/contracts/test_shared_state_contracts.bats`

**Step tasks:**

1. 更新 roadmap 初始化模板，补齐当前标准要求的默认结构。
2. 新增 roadmap item 时默认写入：
   - `github_project_item_id: null`
   - `content_type: "draft_issue"` 或当前标准允许的默认值
   - `execution_record_id: null`
   - `spec_standard: "none"`
   - `spec_ref: null`
3. 保留 `source_type/source_refs` 作为来源层，不让 `content_type` 覆盖来源语义。
4. 为新增与初始化路径补 fixture 断言。

**Expected Result:**
- 任何新建 roadmap item 都直接满足当前共享真源标准。

## Task 2: 补齐 roadmap 查询输出契约

**Files:**
- Modify: `lib/roadmap_query.sh`
- Create: `tests/contracts/test_shared_state_contracts.bats`

**Step tasks:**

1. 为 `list --json`、`show --json`、`status --json` 增加新字段保留。
2. 人类可读输出中显式区分：
   - GitHub 官方层
   - Vibe 扩展层
3. 保证旧调用方不因字段缺失而继续推导旧语义。
4. 用测试锁定 JSON 输出字段存在性与 null 行为。

**Expected Result:**
- roadmap 查询命令可以直接作为 shell/skill 上层的结构化输入。

## Task 3: 补齐 execution record 扩展字段写入

**Files:**
- Modify: `lib/task_actions.sh`
- Modify: `lib/task_write.sh`
- Modify: `tests/task/test_task_ops.bats`
- Modify: `tests/task/test_task_helper.zsh`

**Step tasks:**

1. 让 `task add` 默认写入 `spec_standard/spec_ref`。
2. 让 `task update` 支持稳定更新这两个字段。
3. 确保 task 镜像文件与 registry 主记录保持一致。
4. 加入反向保护，拒绝写入 GitHub item 身份字段。

**Expected Result:**
- task 持有的是 execution spec，而不是 GitHub Project item 身份。

## Task 4: 补齐 execution record 查询与聚合输出

**Files:**
- Modify: `lib/task_query.sh`
- Modify: `tests/task/test_task_sync.bats`
- Create: `tests/contracts/test_shared_state_contracts.bats`

**Step tasks:**

1. 统一 `task list/show --json` 的扩展字段结构。
2. 校准 OpenSpec 等聚合输出，使其映射到 `spec_standard/spec_ref`。
3. 确保聚合对象结构兼容 registry task 的最小字段集。
4. 为聚合场景增加输出一致性断言。

**Expected Result:**
- execution record 与聚合输出在结构上可被统一消费。

## Task 5: 建立共享真源交叉断言

**Files:**
- Create: `tests/contracts/test_shared_state_contracts.bats`
- Modify: `tests/task/test_task_ops.bats`
- Modify: `tests/task/test_task_sync.bats`

**Step tasks:**

1. 用 fixture 锁定 roadmap item 必有的 GitHub 官方锚点与 Vibe 扩展字段。
2. 用 fixture 锁定 task 不得出现 GitHub item 官方身份字段。
3. 用 fixture 锁定 worktree 记录不扩散 GitHub Project 身份字段。

**Expected Result:**
- 共享真源的数据边界被测试固定，不再依赖文档记忆。

## Test Command

```bash
bats tests/task/test_task_ops.bats
bats tests/task/test_task_sync.bats
bats tests/contracts/test_shared_state_contracts.bats
```

## Expected Result

- `roadmap.json` 以 GitHub Project 官方对象为规划镜像。
- `registry.json` 以 execution record 为执行镜像。
- `worktrees.json` 保持 runtime-only，不承载规划身份。

## Estimated Change Summary

- Modified: 7 files
- Added: 1 files
- Added/Changed Lines: ~180-300 lines
- Risk: 中等
- Main risk:
  - 现有 query 输出一旦新增字段，可能暴露历史 fixture 的隐含假设
  - 若没有反向断言，task 很容易再次越权承载 GitHub item 身份字段
