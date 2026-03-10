---
document_type: plan
title: Shared State GitHub Project Alignment Plan
status: draft
scope: shared-state
author: Codex GPT-5
created: 2026-03-10
last_updated: 2026-03-10
related_docs:
  - docs/standards/data-model-standard.md
  - docs/standards/roadmap-json-standard.md
  - docs/standards/registry-json-standard.md
  - docs/references/github_project.md
  - docs/plans/2026-03-10-github-project-semantics-readiness-audit.md
---

# Shared State GitHub Project Alignment Plan

**Goal:** 把本地共享真源收敛到“GitHub 官方字段 + Vibe 扩展字段”双层模型，使 `roadmap.json` / `registry.json` / `worktrees.json` 能稳定承载双向同步所需的最小信息。

**Non-Goals:**
- 本计划不实现 GitHub API 调用。
- 本计划不改 slash/workflow 文案。
- 本计划不处理一次性历史回填脚本。

**Tech Stack:** Zsh, jq, `.git/vibe/*.json`, Bats tests, GitHub Project semantics

---

## Current Assessment

当前标准层已经定义了 `github_project_item_id`、`content_type`、`spec_standard`、`execution_record_id`、`spec_ref` 等字段，但共享真源实现仍停留在旧 schema：

1. `lib/roadmap_write.sh` 初始化和新增逻辑仍只写老字段，未写 GitHub 对齐字段和 Vibe 扩展字段。
2. `lib/roadmap_query.sh` 的 `status/list/show` 还没有把新字段纳入 JSON 输出和展示语义。
3. `lib/task_write.sh` / `lib/task_query.sh` 还没有把 `spec_standard`、`spec_ref` 纳入读写与渲染。
4. 现有测试 fixture 仍是旧 schema，无法锁定新字段契约。

## Target Decision

本计划要产出的不是最终同步流程，而是共享真源的稳定 schema 落地：

1. `roadmap.json` 必须原生承载 GitHub 对齐字段：`github_project_item_id`、`content_type`。
2. `roadmap.json` 必须承载允许双向同步的扩展字段：`spec_standard`、`execution_record_id`、`spec_ref`。
3. `registry.json` 必须承载 execution record 的扩展字段：`spec_standard`、`spec_ref`，但不得复制 GitHub item 身份字段。
4. `worktrees.json` 继续只承载 runtime 现场，不引入 GitHub Project 身份字段。

## Files To Modify

- Modify: `lib/roadmap_write.sh`
- Modify: `lib/roadmap_query.sh`
- Modify: `lib/task_write.sh`
- Modify: `lib/task_query.sh`
- Modify: `tests/test_roadmap.bats`
- Modify: `tests/test_task_ops.bats`
- Modify: `tests/test_task_sync.bats`
- Modify: `tests/test_task_helper.zsh`

## Task 1: 落地 `roadmap.json` 新字段写入契约

**Files:**
- Modify: `lib/roadmap_write.sh`
- Test: `tests/test_roadmap.bats`

**Step tasks:**

1. 更新 `_vibe_roadmap_init` 的空文件模板，补齐根字段默认值与 item 级新字段预期。
2. 更新 `_vibe_roadmap_add`，新增 item 时写入：
   - `github_project_item_id: null`
   - `content_type: "draft_issue"`
   - `spec_standard: "none"`
   - `execution_record_id: null`
   - `spec_ref: null`
3. 保持 `source_type` / `source_refs` 与新字段分层，不让 `content_type` 取代 `source_type`。
4. 为 `roadmap add` / `roadmap sync` fixture 增加断言，确保新字段稳定存在。

**Expected Result:**
- 新建 roadmap item 时立即满足新标准 schema。
- roadmap fixture 不再依赖旧字段最小集。

## Task 2: 落地 `roadmap.json` 新字段读取契约

**Files:**
- Modify: `lib/roadmap_query.sh`
- Test: `tests/test_roadmap.bats`

**Step tasks:**

1. 更新 `status --json` 输出，使其在不破坏现有使用方的前提下包含可扩展元信息。
2. 更新 `list --json` / `show --json`，直接返回含 `content_type`、`github_project_item_id`、`spec_standard`、`execution_record_id`、`spec_ref` 的 item。
3. 更新人类可读 `show` 文案，增加“GitHub 官方层”和“Vibe 扩展层”的展示分组。
4. 新增测试，锁定 `show --json` 和 `list --json` 对新字段的保留行为。

**Expected Result:**
- roadmap 查询类命令能稳定暴露新 schema。
- 后续 shell sync / skill 编排无需再自行拼接这些字段。

## Task 3: 落地 `registry.json` 扩展字段读写契约

**Files:**
- Modify: `lib/task_write.sh`
- Modify: `lib/task_query.sh`
- Modify: `tests/test_task_ops.bats`
- Modify: `tests/test_task_helper.zsh`

**Step tasks:**

1. 扩展 task add 默认写入：
   - `spec_standard: "none"`
   - `spec_ref: null`
2. 扩展 `vibe task update` 的写入路径，支持 `--spec-standard` / `--spec-ref`。
3. 确保 `task.json` 镜像文件也同步这些扩展字段。
4. 明确拒绝把 `github_project_item_id`、`content_type` 写入 task record。
5. 新增测试覆盖：
   - `task add` 默认字段
   - `task update --spec-standard --spec-ref`
   - 去重与 null 行为

**Expected Result:**
- execution record 能表达自身采用的规范体系。
- task record 不会越权承载 GitHub item 身份字段。

## Task 4: 统一 OpenSpec 聚合与 shared-state 输出契约

**Files:**
- Modify: `lib/task_query.sh`
- Modify: `tests/test_task_sync.bats`

**Step tasks:**

1. 更新 `_vibe_task_collect_openspec_tasks` 的临时聚合对象，使其映射到 `spec_standard=openspec`。
2. 为 bridge fallback 数据填充 `spec_ref`。
3. 确保 `vibe task list --json` 输出中，OpenSpec 聚合任务与 registry tasks 的扩展字段结构一致。
4. 补测试锁定 OpenSpec 聚合输出字段。

**Expected Result:**
- 聚合任务与本地 registry task 在输出上具备统一扩展字段。

## Task 5: 共享真源交叉校验

**Files:**
- Modify: `tests/test_roadmap.bats`
- Modify: `tests/test_task_ops.bats`
- Modify: `tests/test_task_sync.bats`

**Step tasks:**

1. 为 roadmap / task fixture 升级到 `schema_version: "v2"`。
2. 添加 schema 级断言，检查新增字段存在性与默认值。
3. 添加反向断言，确认 task record 中不出现 `content_type`、`github_project_item_id`。

**Expected Result:**
- 共享真源层对新标准的读写契约被测试锁住。

## Test Command

```bash
bats tests/test_roadmap.bats
bats tests/test_task_ops.bats
bats tests/test_task_sync.bats
```

## Expected Result

- `roadmap.json` 与 `registry.json` 的实现层 schema 对齐标准文件。
- roadmap item 能稳定承载 GitHub 官方字段和 Vibe 扩展字段。
- task execution record 只承载执行扩展字段，不越权复制 GitHub item 身份。

## Estimated Change Summary

- Modified: 8 files
- Added: ~120-220 lines
- Removed: ~20-60 lines
- Risk: 中等
- Main risk:
  - 旧 fixture 大量假定最小 schema，升级时容易连锁失败
  - `roadmap_query` 与 `task_query` 的 JSON 输出一旦变化，可能影响现有 skill 消费端
