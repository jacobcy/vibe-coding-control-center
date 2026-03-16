---
document_type: plan
title: Shell Command GitHub Project Refactor Plan
status: draft
scope: shell
author: Codex GPT-5
created: 2026-03-10
last_updated: 2026-03-10
related_docs:
  - docs/references/github_project.md
  - docs/standards/v2/command-standard.md
  - docs/standards/v2/data-model-standard.md
  - docs/standards/v2/skill-standard.md
---

# Shell Command GitHub Project Refactor Plan

**Goal:** 把 `vibe roadmap`、`vibe task`、`vibe flow` 的命令契约收敛到当前 GitHub Project 兼容语义，使 shell API 能稳定表达规划层、执行层和 runtime 层边界。

**Non-Goals:**
- 本计划不改技能文案。
- 本计划不实现完整 GitHub Project bootstrap。
- 本计划不做历史数据迁移。

**Tech Stack:** Zsh, jq, gh CLI, `bin/vibe`, `lib/roadmap*.sh`, `lib/task*.sh`, `lib/flow*.sh`, Bats

---

## Current Assessment

标准层已经定义了对象边界，但 shell 命令实现还需要进一步落地。旧方案的主要过时点有两个：一是默认假设存在 `tests/test_flow.bats` 等测试文件，二是对 `roadmap sync` 的描述还不够严格。当前需要补的是命令契约，而不是再次造术语。

当前壳层应满足以下事实：

1. `vibe roadmap` 管理 mirrored GitHub Project item。
2. `vibe task` 是 execution record 的唯一写入口。
3. `vibe flow` 只消费 task，不创建规划对象。
4. help、JSON 输出和退出码都需要体现这些边界。

## Target Decision

1. `roadmap sync` 收敛为 Project-first，同步 repo issue 仅作为兼容导入或来源补充。
2. `task add/update` 显式支持 `spec_standard/spec_ref`，并拒绝 GitHub item 身份字段。
3. `flow` 绑定前校验 task 语义，不再暗示 feature/roadmap type 身份。
4. CLI 帮助文案必须与当前标准完全一致。

## Files To Modify

- Modify: `bin/vibe`
- Modify: `lib/roadmap.sh`
- Modify: `lib/roadmap_help.sh`
- Modify: `lib/roadmap_write.sh`
- Modify: `lib/roadmap_query.sh`
- Modify: `lib/task.sh`
- Modify: `lib/task_help.sh`
- Modify: `lib/task_actions.sh`
- Modify: `lib/task_write.sh`
- Modify: `lib/task_query.sh`
- Modify: `lib/flow.sh`
- Modify: `lib/flow_help.sh`
- Modify: `tests/task/test_task_ops.bats`
- Modify: `tests/task/test_task_sync.bats`
- Modify: `tests/contracts/check_help.sh`
- Create: `tests/contracts/test_roadmap_contract.bats`
- Create: `tests/contracts/test_flow_contract.bats`

## Task 1: 收紧 `vibe roadmap sync` 入口

**Files:**
- Modify: `lib/roadmap.sh`
- Modify: `lib/roadmap_help.sh`
- Modify: `lib/roadmap_write.sh`
- Modify: `lib/roadmap_query.sh`
- Create: `tests/contracts/test_roadmap_contract.bats`

**Step tasks:**

1. 明确 `sync` 的默认语义是 GitHub Project item mirror。
2. 将 repo issue 导入路径标记为兼容模式，而不是主语义。
3. 让 `sync --json` 输出区分：
   - GitHub 官方字段同步结果
   - Vibe 扩展字段同步结果
4. 为 help 与 JSON 输出补回归测试。

**Expected Result:**
- `roadmap sync` 不再被视为 issue-first 导入器。

## Task 2: 让 `vibe task` 成为 execution spec 唯一入口

**Files:**
- Modify: `lib/task.sh`
- Modify: `lib/task_help.sh`
- Modify: `lib/task_actions.sh`
- Modify: `lib/task_write.sh`
- Modify: `lib/task_query.sh`
- Modify: `tests/task/test_task_ops.bats`

**Step tasks:**

1. 在 `task add/update` 中支持 `--spec-standard`、`--spec-ref`。
2. 校验允许值与 null 行为。
3. 显式拒绝通过 `task` 写入 `github_project_item_id/content_type`。
4. 在 `show/list --json` 中保留 execution spec 字段，供上层消费。

**Expected Result:**
- 所有 execution spec 更新都必须经过 `vibe task`。

## Task 3: 收紧 `vibe flow` 只消费 execution record

**Files:**
- Modify: `lib/flow.sh`
- Modify: `lib/flow_help.sh`
- Create: `tests/contracts/test_flow_contract.bats`

**Step tasks:**

1. 强化 `flow new`、`flow bind` 的帮助文案，明确前置条件是已有 task。
2. 在 bind/new 的关键路径增加 task 状态与存在性校验。
3. 让 `flow status --json` 暴露 task 摘要字段，但不复制 roadmap identity。
4. 为 flow contract 增加最小测试。

**Expected Result:**
- flow 是 runtime 容器，不再混入 roadmap item 或 feature type 语义。

## Task 4: 更新顶层帮助和退出码契约

**Files:**
- Modify: `bin/vibe`
- Modify: `lib/roadmap_help.sh`
- Modify: `lib/task_help.sh`
- Modify: `lib/flow_help.sh`
- Modify: `tests/contracts/check_help.sh`

**Step tasks:**

1. 顶层 help 明确三层对象：
   - roadmap item = planning mirror
   - task = execution record
   - flow = runtime container
2. 避免任何帮助文案继续把 `type=task` 说成本地 task。
3. 锁定帮助文案中的关键术语与错误退出码。

**Expected Result:**
- 用户从 help 即可看见当前对象模型，而不是旧项目语义。

## Task 5: 建立 shell contract 回归

**Files:**
- Create: `tests/contracts/test_roadmap_contract.bats`
- Create: `tests/contracts/test_flow_contract.bats`
- Modify: `tests/task/test_task_ops.bats`
- Modify: `tests/task/test_task_sync.bats`
- Modify: `tests/contracts/check_help.sh`

**Step tasks:**

1. 对 roadmap/task/flow 的关键 JSON 输出做字段存在性断言。
2. 对帮助文案做 grep 级断言。
3. 对拒绝非法字段写入的错误路径补测试。

**Expected Result:**
- shell 语义与标准文件保持同步，并在回归测试中可见。

## Test Command

```bash
bats tests/task/test_task_ops.bats
bats tests/task/test_task_sync.bats
bats tests/contracts/test_roadmap_contract.bats
bats tests/contracts/test_flow_contract.bats
bash tests/contracts/check_help.sh
```

## Expected Result

- `vibe roadmap`、`vibe task`、`vibe flow` 的边界与 GitHub Project 兼容标准一致。
- CLI 输出不再鼓励用户使用项目自造语义解释 GitHub 官方对象。

## Estimated Change Summary

- Modified: 15 files
- Added: 2 files
- Added/Changed Lines: ~220-360 lines
- Risk: 中高
- Main risk:
  - 帮助文案与 JSON 输出一旦变化，现有 skill 消费端可能暴露隐含依赖
  - 若 `roadmap sync` 兼容路径处理不严，容易再次回退到 issue-first 语义
