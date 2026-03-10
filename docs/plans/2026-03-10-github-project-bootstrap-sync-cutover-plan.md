---
document_type: plan
title: GitHub Project Bootstrap Sync Cutover Plan
status: draft
scope: migration
author: Codex GPT-5
created: 2026-03-10
last_updated: 2026-03-10
related_docs:
  - docs/standards/data-model-standard.md
  - docs/standards/roadmap-json-standard.md
  - docs/standards/registry-json-standard.md
  - docs/standards/command-standard.md
  - docs/references/github_project.md
---

# GitHub Project Bootstrap Sync Cutover Plan

**Goal:** 设计一次性把现有共享真源与 GitHub Project 对接成功的执行方案，完成 schema 补齐、字段映射、预检查、回填、校验和回滚预案。

**Non-Goals:**
- 本计划不定义长期产品规划流程。
- 本计划不重构全部历史 worktree 记录。
- 本计划不处理多仓库场景。

**Tech Stack:** Zsh, jq, gh CLI, GitHub GraphQL/REST, `.git/vibe/*.json`, one-off migration scripts, Bats smoke checks

---

## Current Assessment

当前项目要“一次性对接成功”，真正风险不在新字段本身，而在历史数据和 GitHub 真实项目状态之间的偏差：

1. 现有 `roadmap.json` 里很多 item 仍是 repo issue mirror，而不是 Project item mirror。
2. 现有 `registry.json` 里 task 还没有统一的 `spec_standard/spec_ref`。
3. 现有 GitHub Project 上未必已经存在所需 custom fields。
4. 若直接同步，容易出现：
   - 本地覆盖 GitHub
   - GitHub 覆盖本地
   - task 与 roadmap bridge 丢失

## Target Decision

1. 先做只读审计，再做字段建模，再做一次性回填，最后切换到双向同步。
2. `github_project_item_id + content_type` 是 GitHub 官方锚点。
3. `execution_record_id + spec_standard + spec_ref` 是 Vibe 扩展锚点。
4. migration 必须具备 dry-run、snapshot、rollback 三件套。

## Files To Modify

- Create: `scripts/github_project_bootstrap_sync.sh`
- Create: `scripts/github_project_field_map.sh`
- Modify: `lib/roadmap_write.sh`
- Modify: `lib/roadmap_query.sh`
- Modify: `lib/check.sh`
- Modify: `lib/check_groups.sh`
- Modify: `tests/test_roadmap.bats`
- Modify: `tests/test_task_ops.bats`
- Modify: `tests/check_help.sh`
- Create: `artifacts/github-project-bootstrap/README.md`

## Task 1: 设计一次性同步前置审计

**Files:**
- Create: `scripts/github_project_bootstrap_sync.sh`
- Modify: `lib/check.sh`
- Modify: `lib/check_groups.sh`

**Step tasks:**

1. 增加 dry-run 模式，只读取：
   - GitHub Project items
   - custom fields
   - 本地 roadmap/task 数据
2. 输出审计报告：
   - 缺少 `github_project_item_id` 的 roadmap item
   - 无 `execution_record_id` 的 roadmap item
   - task 缺失 `spec_standard/spec_ref`
   - GitHub Project 缺失 custom fields
3. 审计报告写入 `artifacts/github-project-bootstrap/`。

**Expected Result:**
- 能在真正回填前知道差距和阻塞项。

## Task 2: 设计 GitHub Project 字段映射与建场步骤

**Files:**
- Create: `scripts/github_project_field_map.sh`
- Create: `artifacts/github-project-bootstrap/README.md`

**Step tasks:**

1. 明确必需 custom fields：
   - `spec_standard`
   - `execution_record_id`
   - `spec_ref`
2. 为每个字段定义：
   - GitHub 类型
   - 合法值
   - 本地字段来源
3. 输出建场步骤：
   - 如何检测字段是否已存在
   - 如何创建缺失字段
   - 如何记录 field id 供后续同步使用

**Expected Result:**
- 一次性对接前，GitHub Project 端具备接收 Vibe 扩展字段的结构。

## Task 3: 回填 roadmap 与 task 桥接字段

**Files:**
- Create: `scripts/github_project_bootstrap_sync.sh`
- Modify: `lib/roadmap_write.sh`
- Modify: `lib/roadmap_query.sh`

**Step tasks:**

1. 先为本地 roadmap item 回填：
   - `github_project_item_id`
   - `content_type`
   - `execution_record_id`
2. 再为本地 task 回填：
   - `spec_standard`
   - `spec_ref`
3. 生成 before/after snapshot，保存在 artifact 目录。
4. 每一步都支持 `--dry-run` 和 `--apply`。

**Expected Result:**
- 本地共享真源具备完整双向同步锚点。

## Task 4: 执行一次性 push/pull 对齐

**Files:**
- Create: `scripts/github_project_bootstrap_sync.sh`
- Modify: `lib/roadmap_write.sh`

**Step tasks:**

1. 先 pull GitHub Project 官方字段到本地。
2. 再 push 本地扩展字段到 GitHub Project custom fields。
3. 冲突时按以下优先级：
   - 官方身份字段以 GitHub 为准
   - execution spec 扩展字段以本地为准，但记录冲突
4. 输出最终 reconciliation 报告。

**Expected Result:**
- 本地与 GitHub Project 完成首次一致化。

## Task 5: 收尾验证与回滚预案

**Files:**
- Modify: `lib/check.sh`
- Modify: `tests/test_roadmap.bats`
- Modify: `tests/test_task_ops.bats`
- Modify: `tests/check_help.sh`

**Step tasks:**

1. 增加一个 bootstrap 后校验入口，检查：
   - roadmap item 的 GitHub 锚点完整
   - task execution spec 完整
   - custom fields 与本地值一致
2. 提供回滚步骤：
   - 恢复本地 snapshot
   - 停止同步脚本
   - 重新执行 dry-run
3. 为脚本参数和帮助文案补最小 smoke test。

**Expected Result:**
- 一次性对接有明确的成功标准和失败回退路径。

## Test Command

```bash
zsh scripts/github_project_bootstrap_sync.sh --dry-run
zsh scripts/github_project_field_map.sh --check
bats tests/test_roadmap.bats
bats tests/test_task_ops.bats
bash tests/check_help.sh
```

## Expected Result

- 对接前能识别缺口。
- GitHub Project 端 custom fields 结构完备。
- 本地共享真源与 GitHub Project 完成首次一致化后，可进入常态双向同步。
- 失败时可用 snapshot 回滚。

## Estimated Change Summary

- Modified: 7 files
- Added: 3 files
- Added/Changed Lines: ~220-420 lines
- Risk: 高
- Main risk:
  - 真实 GitHub Project 数据可能比标准假设更脏
  - 一次性对接脚本若没有 dry-run/snapshot，容易造成双边数据污染
