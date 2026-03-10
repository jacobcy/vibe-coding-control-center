---
document_type: plan
title: Shell Command GitHub Project Refactor Plan
status: draft
scope: shell
author: Codex GPT-5
created: 2026-03-10
last_updated: 2026-03-10
related_docs:
  - docs/standards/command-standard.md
  - docs/standards/roadmap-json-standard.md
  - docs/standards/registry-json-standard.md
  - docs/references/github_project.md
---

# Shell Command GitHub Project Refactor Plan

**Goal:** 把 `vibe roadmap` / `vibe task` / `vibe flow` 的实现改造成符合新标准层语义的原子命令接口，为后续 skill 与双向同步提供稳定 Shell API。

**Non-Goals:**
- 本计划不直接改 skill 文案。
- 本计划不完成一次性历史数据迁移。
- 本计划不实现完整 GitHub Project 同步脚本，只补命令契约与最小执行路径。

**Tech Stack:** Zsh, jq, gh CLI, Bats, `bin/vibe`, `lib/roadmap*.sh`, `lib/task*.sh`, `lib/flow*.sh`

---

## Current Assessment

当前命令实现与标准层仍有四个缺口：

1. `vibe roadmap sync` 仍是“按 label 拉 repo issue”语义，还不是 GitHub Project item 同步。
2. `vibe task add/update` 还不能显式管理 `spec_standard` / `spec_ref`。
3. `vibe flow new/bind` 文案已经纠偏，但底层没有强制校验 execution record 与 roadmap item 的桥接状态。
4. help/usage 文案和 JSON 输出尚未体现“官方字段 vs 扩展字段”的层级。

## Target Decision

1. `vibe roadmap sync` 先收敛为 GitHub Project item 镜像同步入口，保留 repo issue 兼容路径但明确降级。
2. `vibe task` 成为管理 execution record 扩展字段的唯一合法入口。
3. `vibe flow` 只消费已有 task record，不替代规划或同步动作。
4. 所有命令帮助文案都要反映新的对象分层。

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
- Modify: `lib/flow.sh`
- Modify: `lib/flow_help.sh`
- Modify: `tests/test_roadmap.bats`
- Modify: `tests/test_task_ops.bats`
- Modify: `tests/test_flow.bats`

## Task 1: 重写 `vibe roadmap sync` 命令边界

**Files:**
- Modify: `lib/roadmap.sh`
- Modify: `lib/roadmap_help.sh`
- Modify: `lib/roadmap_write.sh`
- Test: `tests/test_roadmap.bats`

**Step tasks:**

1. 调整 `sync` 参数设计，显式区分：
   - GitHub Project item 同步路径
   - repo issue label 兼容导入路径
2. 将默认说明改为“Project-first”，把现有 repo issue 镜像路径标记为兼容模式。
3. 为 sync 返回结果增加：
   - 新增/更新 item 数
   - 官方字段同步结果
   - 扩展字段同步结果
4. 新增 help 和测试，锁定 `--provider github --repo ...` 的语义提示。

**Expected Result:**
- `vibe roadmap sync` 不再被误解为 issue-first 导入器。

## Task 2: 扩展 `vibe task add/update` 为规范字段入口

**Files:**
- Modify: `lib/task.sh`
- Modify: `lib/task_help.sh`
- Modify: `lib/task_actions.sh`
- Modify: `lib/task_write.sh`
- Test: `tests/test_task_ops.bats`

**Step tasks:**

1. 在 `task add` 支持 `--spec-standard`、`--spec-ref`。
2. 在 `task update` 支持更新 `spec_standard`、`spec_ref`。
3. 明确枚举校验：
   - `openspec`
   - `kiro`
   - `superpowers`
   - `supervisor`
   - `none`
4. 明确拒绝写入 GitHub item 官方字段。
5. 更新 help 文案与 JSON 输出测试。

**Expected Result:**
- `vibe task` 成为 execution record 扩展字段的标准入口。

## Task 3: 收紧 `vibe flow` 的消费边界

**Files:**
- Modify: `lib/flow.sh`
- Modify: `lib/flow_help.sh`
- Test: `tests/test_flow.bats`

**Step tasks:**

1. 保留 `flow new` 只创建现场的行为，并把帮助文案进一步收紧到“必须先有 task record”。
2. 在 `flow bind` 前增加最小校验：
   - task 存在
   - task 状态允许绑定
   - task 若已有 `spec_standard`，绑定日志中展示出来
3. 在 `flow status --json` 中透出 task 的 `spec_standard` / `spec_ref` 摘要，便于 skill 消费。
4. 补测试锁定：
   - bind 时不创建 task
   - bind 时保留 execution record 语义

**Expected Result:**
- flow 命令继续只做 runtime orchestration，不偷渡规划逻辑。

## Task 4: 更新 CLI 顶层帮助与命令叙述

**Files:**
- Modify: `bin/vibe`
- Modify: `lib/roadmap_help.sh`
- Modify: `lib/task_help.sh`
- Modify: `lib/flow_help.sh`

**Step tasks:**

1. 更新顶层 `vibe help`，反映：
   - roadmap = GitHub Project 镜像与规划层
   - task = execution record
   - flow = 现场编排
2. 在各子命令 help 中补充“官方字段 vs 扩展字段”的说明。
3. 避免任何帮助文案再把 `task` 和 `type=task` 混用。

**Expected Result:**
- Shell 层对外口径与标准文件一致。

## Task 5: Shell 回归测试

**Files:**
- Modify: `tests/test_roadmap.bats`
- Modify: `tests/test_task_ops.bats`
- Modify: `tests/test_flow.bats`

**Step tasks:**

1. 为 roadmap/task/flow 新参数和帮助文案补测试。
2. 跑 targeted bats，确保新参数没有破坏现有基本路径。
3. 对 JSON 输出做最小 snapshot 断言。

**Expected Result:**
- 命令层变更具备最小回归保护。

## Test Command

```bash
bats tests/test_roadmap.bats
bats tests/test_task_ops.bats
bats tests/test_flow.bats
```

## Expected Result

- Shell 命令边界与标准层一致。
- `vibe roadmap sync` 被收敛为 GitHub Project-first 入口。
- `vibe task` 成为扩展字段写入入口。
- `vibe flow` 只消费 execution record，不重新发明对象层级。

## Estimated Change Summary

- Modified: 14 files
- Added: ~180-320 lines
- Removed: ~40-110 lines
- Risk: 中高
- Main risk:
  - help/JSON 输出改动可能影响 skill 消费端
  - sync 子命令从 issue-first 向 project-first 收敛时，兼容路径容易被误删
