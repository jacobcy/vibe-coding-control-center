---
document_type: plan
title: GitHub Project Bootstrap Sync Cutover Plan
status: draft
scope: migration
author: Codex GPT-5
created: 2026-03-10
last_updated: 2026-03-10
related_docs:
  - docs/references/github_project.md
  - docs/standards/v2/command-standard.md
  - docs/standards/v2/data-model-standard.md
  - docs/standards/v2/roadmap-json-standard.md
  - docs/standards/v2/registry-json-standard.md
---

# GitHub Project Bootstrap Sync Cutover Plan

**Goal:** 设计一套可执行的 GitHub Project 启动同步与切换方案，让本地共享真源在不改写 GitHub 官方对象语义的前提下，逐步接入 GitHub Project 作为规划层真源。

**Non-Goals:**
- 本计划不实现长期双向实时同步。
- 本计划不清洗全部历史数据。
- 本计划不改 skill 文案或 workflow 编排。

**Tech Stack:** Zsh, jq, gh CLI, GitHub GraphQL, `.git/vibe/*.json`, Bats, audit artifacts

---

## Current Assessment

主线标准已经完成语义纠偏，但“如何真正切到 GitHub Project”仍缺一个可落地 cutover 方案。旧方案的问题是把 cutover 假定成一次性双向同步，而当前标准要求更严格：

1. `roadmap item` 是 mirrored GitHub Project item，不是 repo issue mirror。
2. `task` 是 execution record，只能承载 `spec_standard/spec_ref` 等 Vibe 扩展字段。
3. GitHub 官方字段与 Vibe 扩展字段必须分层同步，不能互相改写身份。
4. 当前仓库还没有 bootstrap 脚本、字段探测脚本和对应的最小回归测试。

因此当前需要的不是“直接上线同步”，而是一个分阶段、可 dry-run、可回滚的 cutover 实施方案。

## Target Decision

1. cutover 分成 `read-only audit -> field readiness -> dry-run reconcile -> apply -> verify` 五段。
2. GitHub Project 官方身份字段以 GitHub 返回值为准：
   - `github_project_item_id`
   - `content_type`
   - GitHub 原生状态/字段映射
3. Vibe 仅追加扩展桥接字段，不改写 GitHub 官方类型：
   - `execution_record_id`
   - `spec_standard`
   - `spec_ref`
4. 首次 cutover 只支持 Project-first，同步 repo issue 仅作为来源补充，不作为主身份来源。

## Files To Modify

- Create: `scripts/github_project_bootstrap_sync.sh`
- Create: `scripts/github_project_field_map.sh`
- Create: `tests/contracts/test_github_project_bootstrap.bats`
- Modify: `lib/roadmap_write.sh`
- Modify: `lib/roadmap_query.sh`
- Modify: `lib/check.sh`
- Modify: `lib/check_groups.sh`
- Modify: `tests/task/test_task_sync.bats`
- Create: `artifacts/github-project-bootstrap/README.md`

## Task 1: 建立只读 readiness audit

**Files:**
- Create: `scripts/github_project_bootstrap_sync.sh`
- Modify: `lib/check.sh`
- Modify: `lib/check_groups.sh`

**Step tasks:**

1. 为 bootstrap 脚本实现只读模式，读取：
   - GitHub Project items
   - GitHub Project custom fields
   - 本地 `roadmap.json`
   - 本地 `registry.json`
2. 输出 readiness 报告，至少识别：
   - 缺失 `github_project_item_id` 的 roadmap item
   - 缺失 `content_type` 的 roadmap item
   - 缺失 `execution_record_id` 的 roadmap item
   - 缺失 `spec_standard/spec_ref` 的 task
3. 将审计结果写入 `artifacts/github-project-bootstrap/`，供 apply 前人工复核。

**Expected Result:**
- 在任何写操作之前，先看见当前主线数据与 GitHub Project 真实状态的差距。

## Task 2: 固化 GitHub Project 字段就绪检查

**Files:**
- Create: `scripts/github_project_field_map.sh`
- Create: `artifacts/github-project-bootstrap/README.md`

**Step tasks:**

1. 固化当前 cutover 所需的 GitHub Project 字段清单。
2. 区分：
   - GitHub 官方字段
   - Vibe 扩展字段承载方式
3. 为扩展字段定义：
   - GitHub Project custom field 类型
   - 合法值范围
   - 与本地字段的映射关系
4. 输出缺失字段的创建步骤和后续脚本需要使用的 field id 记录格式。

**Expected Result:**
- cutover 前能够确认 GitHub Project 端结构已经准备完毕。

## Task 3: 实现 dry-run reconcile

**Files:**
- Create: `scripts/github_project_bootstrap_sync.sh`
- Modify: `lib/roadmap_write.sh`
- Modify: `lib/roadmap_query.sh`
- Modify: `tests/contracts/test_github_project_bootstrap.bats`

**Step tasks:**

1. 让 bootstrap 脚本在 dry-run 下生成：
   - GitHub -> local 官方字段更新提案
   - local -> GitHub 扩展字段写回提案
2. 明确冲突规则：
   - 官方身份字段以 GitHub 为准
   - Vibe 扩展字段以本地为准，但必须记录冲突
3. 输出 before/after preview，不直接修改任何本地 JSON 或 GitHub Project 数据。
4. 为 dry-run 输出添加最小测试，锁定报告格式与退出码。

**Expected Result:**
- 在真正 apply 之前，能够预览 reconciliation 结果和冲突点。

## Task 4: 实现受控 apply 与 snapshot

**Files:**
- Create: `scripts/github_project_bootstrap_sync.sh`
- Modify: `lib/roadmap_write.sh`
- Modify: `tests/task/test_task_sync.bats`

**Step tasks:**

1. apply 前生成本地 snapshot。
2. 先落 GitHub 官方字段到本地 roadmap item。
3. 再把 Vibe 扩展字段写回 GitHub Project custom fields。
4. apply 完成后生成 reconciliation report，记录：
   - 成功更新数
   - 冲突数
   - 跳过数
   - 失败原因

**Expected Result:**
- 首次切换具备顺序化 apply、snapshot 和冲突报告。

## Task 5: 增加 cutover 后核验与回滚入口

**Files:**
- Modify: `lib/check.sh`
- Modify: `lib/check_groups.sh`
- Create: `tests/contracts/test_github_project_bootstrap.bats`

**Step tasks:**

1. 为 `vibe check` 增加 GitHub Project cutover 校验组。
2. 校验项至少包含：
   - roadmap item 官方锚点完整
   - task execution spec 完整
   - task 不持有 GitHub item 身份字段
3. 在 artifact README 中记录本地 snapshot 恢复步骤与 rerun 顺序。

**Expected Result:**
- cutover 完成后有明确成功标准，失败时有明确恢复路径。

## Test Command

```bash
zsh scripts/github_project_field_map.sh --check
zsh scripts/github_project_bootstrap_sync.sh --dry-run
bats tests/contracts/test_github_project_bootstrap.bats
bats tests/task/test_task_sync.bats
```

## Expected Result

- cutover 以 GitHub Project 官方语义为基础，而不是本地自造对象语义。
- 首次同步具备 field readiness、dry-run、apply、snapshot、rollback 全链路。
- `roadmap item` 与 `task` 的边界在同步实现中继续保持清晰。

## Estimated Change Summary

- Modified: 4 files
- Added: 5 files
- Added/Changed Lines: ~260-420 lines
- Risk: 高
- Main risk:
  - GitHub Project 实际字段形态可能与文档假设不完全一致
  - 首次 apply 若缺少 dry-run 报告，容易污染 GitHub 官方字段与本地桥接字段
