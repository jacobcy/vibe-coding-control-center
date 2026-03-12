---
document_type: plan
title: gh-112 cli output summary
status: proposed
scope: issue-112-cli-observability
author: Codex GPT-5
created: 2026-03-11
last_updated: 2026-03-11
related_issues:
  - gh-112
related_docs:
  - lib/task.sh
  - lib/task_query.sh
  - lib/flow.sh
  - lib/flow_show.sh
  - lib/roadmap.sh
  - lib/roadmap_help.sh
  - tests/task/test_task_ops.bats
  - tests/flow/test_flow_help_runtime.bats
  - tests/contracts/test_roadmap_contract.bats
---

# GH-112 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 为 `vibe task`、`vibe flow`、`vibe roadmap` 的关键成功路径补齐稳定执行摘要，降低 agent 在成功后还要二次 `show/status/list` 补上下文的成本。

**Architecture:** 只在现有 shell 子命令成功路径上补统一摘要输出，不新增新的共享状态结构，也不把 workflow 逻辑下沉到 shell。优先复用现有 `show/status/list` 已有字段，针对写操作输出对象、关键变更、结果状态和下一步建议，对“无结果”查询输出显式空结果文本。

**Tech Stack:** Zsh CLI, existing `lib/*.sh` modules, Bats, `jq`, `rg`

---

## Goal

- 为 `vibe task` 关键写操作和查询空结果补显式摘要
- 为 `vibe flow` 关键运行时命令补显式成功摘要
- 为 `vibe roadmap` 关键命令补显式成功摘要或空结果提示
- 用测试锁定输出契约，避免回退到静默成功

## Non-Goals

- 不新增新的顶层命令或新的共享状态 schema
- 不改造 GitHub Project / registry 数据模型
- 不统一所有历史输出格式到单一 renderer
- 不处理与 `gh-112` 无关的全局审计遗留失败

## Tech Stack

- 语言：Zsh
- 数据处理：`jq`
- 测试：Bats
- 文本扫描：`rg`

## Files To Modify

- `lib/task_actions.sh`
- `lib/task_query.sh`
- `lib/flow.sh`
- `lib/roadmap.sh`
- `lib/roadmap_help.sh`
- `lib/flow_show.sh` 或相关 `flow_*` render helper
- `tests/task/test_task_ops.bats`
- `tests/task/test_task_render.bats`
- `tests/flow/test_flow_help_runtime.bats`
- `tests/contracts/test_roadmap_contract.bats`

## Verification Command

```bash
bats tests/task/test_task_ops.bats
bats tests/task/test_task_render.bats
bats tests/flow/test_flow_help_runtime.bats
bats tests/contracts/test_roadmap_contract.bats
```

## Expected Result

- `vibe task add/update/remove/audit/list/show` 在成功或空结果场景下都有可读且稳定的摘要
- `vibe flow new/bind/show/status/list/done` 成功后能直接说明对象、状态和下一步
- `vibe roadmap show/list/sync/classify/assign/version` 不再出现“成功但几乎没信息”的路径
- 相关 Bats 测试覆盖输出契约并通过

## Commit Plan

1. `test(cli): lock task and flow summary output contracts`
2. `feat(cli): add task and flow success summaries`
3. `feat(cli): add roadmap success and empty-result summaries`

## Task 1: Lock the output contract with failing tests

**Files:**
- Modify: `tests/task/test_task_ops.bats`
- Modify: `tests/task/test_task_render.bats`
- Modify: `tests/flow/test_flow_help_runtime.bats`
- Modify: `tests/contracts/test_roadmap_contract.bats`

**Step 1: Add failing tests for task summaries**

- 为 `vibe task add`、`vibe task update`、`vibe task list --status ...` 无结果场景补断言：
  - 成功时输出 task id、动作结果、关键字段或下一步
  - 无结果时输出稳定文本而不是静默

**Step 2: Add failing tests for flow summaries**

- 为 `vibe flow new`、`vibe flow bind`、`vibe flow done` 或 `show/status` 相关成功路径补断言：
  - 输出 flow 名称或 branch
  - 输出绑定 task / state / next step

**Step 3: Add failing tests for roadmap summaries**

- 为 `vibe roadmap show`、`vibe roadmap list` 空结果或 `sync/classify/version` 成功路径补断言：
  - 输出 roadmap item 标识
  - 输出分类结果或 sync 结果摘要

**Step 4: Run focused tests to confirm failure**

Run:

```bash
bats tests/task/test_task_ops.bats
bats tests/task/test_task_render.bats
bats tests/flow/test_flow_help_runtime.bats
bats tests/contracts/test_roadmap_contract.bats
```

Expected:

- 新增断言失败
- 失败原因是目标摘要尚不存在，而不是 fixture 或语法错误

**Step 5: Commit Task 1**

Run:

```bash
git add tests/task/test_task_ops.bats tests/task/test_task_render.bats tests/flow/test_flow_help_runtime.bats tests/contracts/test_roadmap_contract.bats
git commit -m "test(cli): lock task and flow summary output contracts"
```

Expected:

- 形成只覆盖输出契约测试的一次提交

## Task 2: Implement task and flow success summaries

**Files:**
- Modify: `lib/task_actions.sh`
- Modify: `lib/task_query.sh`
- Modify: `lib/flow.sh`
- Modify: `lib/flow_show.sh` 或相关 `flow_*` helper
- Modify: `tests/task/test_task_ops.bats`
- Modify: `tests/task/test_task_render.bats`
- Modify: `tests/flow/test_flow_help_runtime.bats`

**Step 1: Implement task write-operation summaries**

- 在 `vibe task add/update/remove` 成功后输出稳定摘要：
  - 对象：task id / title
  - 关键变化：status、issue_refs、roadmap_item_ids、spec_ref、绑定现场
  - 结果：成功状态
  - 下一步：保留已有 hint，但不要只有 hint

**Step 2: Implement task empty-result summaries**

- 处理 `vibe task list` 过滤后无结果等成功空集合路径
- 输出稳定文本，例如 `No tasks found.` 并确保对人和 agent 都足够明确

**Step 3: Implement flow success summaries**

- 在 `vibe flow new`、`bind`、`done` 等命令成功后补充摘要：
  - flow / branch
  - 当前 task 或关闭结果
  - 下一步动作

**Step 4: Re-run focused task/flow tests**

Run:

```bash
bats tests/task/test_task_ops.bats
bats tests/task/test_task_render.bats
bats tests/flow/test_flow_help_runtime.bats
```

Expected:

- task / flow 相关测试全部通过

**Step 5: Commit Task 2**

Run:

```bash
git add lib/task_actions.sh lib/task_query.sh lib/flow.sh lib/flow_show.sh tests/task/test_task_ops.bats tests/task/test_task_render.bats tests/flow/test_flow_help_runtime.bats
git commit -m "feat(cli): add task and flow success summaries"
```

Expected:

- 形成只覆盖 task / flow 摘要输出的一次提交

## Task 3: Implement roadmap success and empty-result summaries

**Files:**
- Modify: `lib/roadmap.sh`
- Modify: `lib/roadmap_help.sh`
- Modify: 相关 `lib/roadmap_*` render/query helper（按实际实现点收敛）
- Modify: `tests/contracts/test_roadmap_contract.bats`

**Step 1: Trace current roadmap success paths**

- 确认 `show/list/sync/classify/assign/version` 的现有输出由哪些 helper 负责
- 找到静默成功或信息过薄的路径

**Step 2: Implement roadmap summaries**

- 对关键成功路径补充对象、动作结果、关键状态变化
- 对空结果路径补显式 `no result` 文本
- 保持 `--json` 行为不变，不把人类摘要混入 JSON 输出

**Step 3: Run roadmap contract tests**

Run:

```bash
bats tests/contracts/test_roadmap_contract.bats
```

Expected:

- roadmap 输出契约测试通过

**Step 4: Run full verification suite for this issue**

Run:

```bash
bats tests/task/test_task_ops.bats
bats tests/task/test_task_render.bats
bats tests/flow/test_flow_help_runtime.bats
bats tests/contracts/test_roadmap_contract.bats
```

Expected:

- 与 `gh-112` 相关的输出契约测试全部通过

**Step 5: Commit Task 3**

Run:

```bash
git add lib/roadmap.sh lib/roadmap_help.sh tests/contracts/test_roadmap_contract.bats
git commit -m "feat(cli): add roadmap success and empty-result summaries"
```

Expected:

- 形成只覆盖 roadmap 摘要输出的一次提交

## Risks

### Risk 1: Text contract becomes brittle

- **Impact:** 文案轻微调整就导致测试误报
- **Mitigation:** 测试锁定关键字段和关键词，不锁整段完整句子
- **Rollback Trigger:** 如果测试只能依赖整段 hard-coded 文案，需先收窄契约粒度

### Risk 2: Human-readable summary breaks JSON consumers

- **Impact:** `--json` 输出被污染，现有 skill/脚本失效
- **Mitigation:** 明确只在非 JSON 路径加摘要
- **Rollback Trigger:** 任一 `--json` 契约测试回退失败

### Risk 3: Summary logic spreads across too many modules

- **Impact:** 输出风格继续漂移，后续维护困难
- **Mitigation:** 第一轮只在现有 command entry 或 render helper 上最小补齐，不提前抽象大而全 formatter
- **Rollback Trigger:** 为了统一摘要而引入跨模块重构时，应停止并拆计划

## Change Summary Estimate

- `lib/task_actions.sh`: modify, about 20-35 lines
- `lib/task_query.sh`: modify, about 8-18 lines
- `lib/flow.sh` and related flow helper: modify, about 20-35 lines
- `lib/roadmap.sh` / related helper: modify, about 20-40 lines
- tests: modify, about 30-60 lines

Total estimate:

- added: 80-150 lines
- modified: 20-40 lines
- removed: 0-20 lines
