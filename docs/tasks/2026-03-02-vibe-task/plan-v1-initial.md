---
document_type: task-plan
title: vibe-task unified entry implementation plan
date: 2026-03-02
last_updated: 2026-03-02
status: planning
author: Codex GPT-5
related_docs:
  - docs/tasks/2026-03-02-vibe-task/README.md
  - docs/tasks/2026-03-02-cross-worktree-task-registry/plan-v1-initial.md
  - docs/tasks/2026-03-01-session-lifecycle/plan-v2-phase-2.md
  - bin/vibe
  - lib/task.sh
  - skills/vibe-continue/SKILL.md
  - skills/vibe-check/SKILL.md
  - tests/test_vibe.bats
  - tests/test_task.bats
---

# Vibe Task Unified Entry Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 补齐 `vibe task` 和 `vibe-task` 的统一入口方案，但以当前仓库已有 WIP 为起点继续推进，而不是从零重做。

**Architecture:** 保持 `bin/vibe task` 为唯一底层事实读取入口，负责读取 `$(git rev-parse --git-common-dir)/vibe/registry.json` 与 `worktrees.json` 并输出稳定总览；`skills/vibe-task/SKILL.md` 仅包装 CLI，解释输出并给出“下一步进入哪个 worktree”的建议，不重复解析 shared registry。

**Tech Stack:** Zsh CLI, existing `bin/vibe` dispatcher, `jq`, shared registry JSON under `git-common-dir`, Markdown skill, Bats tests

---

## Goal

- 保持 `vibe task` 为跨 worktree 任务总览的唯一读取入口。
- 新增 `skills/vibe-task/SKILL.md`，让对话层走 CLI 而不是自己读 registry。
- 在当前已有 WIP 基础上补齐缺失测试、错误分支和人工验证步骤。
- 给执行阶段一个可直接照做的、最小范围的任务拆分。

## Non-Goals

- 不改共享 registry schema。
- 不改 `vibe-save`、`vibe-continue`、`vibe-new` 的契约。
- 不实现 `vibe-switch`。
- 不增加 `--json`、过滤、排序、交互选择等扩展参数。
- 不清理或重构当前仓库里与本计划无关的脏文件。

## Current Snapshot

截至 2026-03-02，本仓库已不是“未开始”状态，而是“已有部分实现，计划需要接着写”：

- `bin/vibe` 已经存在 `task)` dispatcher，help 里也已有 `task` 文案。
- `lib/task.sh` 已存在最小可运行实现，当前约 76 行，已满足单文件行数约束。
- `tests/test_vibe.bats` 已包含 help 中出现 `task` 的断言。
- `tests/test_task.bats` 已存在 2 个基础用例：
  - registry 缺失时报错
  - overview 基本渲染成功
- `skills/vibe-task/SKILL.md` 仍不存在，这是当前明确缺口。

因此，执行阶段不应再按“先接 CLI 分发，再创建测试文件”的旧顺序做，而应按“核对已有 WIP -> 补缺口 -> 验证”的顺序推进。

## In-Scope Files

- Modify: `bin/vibe`
- Modify: `lib/task.sh`
- Create: `skills/vibe-task/SKILL.md`
- Modify: `tests/test_vibe.bats`
- Modify: `tests/test_task.bats`

## Out-Of-Scope Dirty Files

当前工作区还有以下未提交变更，但不属于本计划：

- `.agent/workflows/vibe-new.md`
- `skills/vibe-continue/SKILL.md`
- `skills/vibe-save/SKILL.md`
- `scripts/rotate.sh`
- `.agent/skills-handbook.md`

执行时不得顺手整理、回退或混入这些文件。

## CLI Output Contract

默认命令：

```bash
bin/vibe task
```

默认输出格式：

```text
Vibe Task Overview

- wt-claude-refactor
  path: /abs/path
  branch: refactor
  state: active dirty
  task: 2026-03-02-cross-worktree-task-registry
  title: Cross-Worktree Task Registry
  status: done
  current subtask: -
  next step: Review the completed registry design and decide whether to integrate runtime readers into command implementations.
```

约束：

- 总标题固定为 `Vibe Task Overview`
- 每个 worktree 输出一段
- `current_subtask_id = null` 时显示 `-`
- `dirty = true` 显示 `dirty`，否则显示 `clean`
- 若 `worktrees.json.current_task` 在 `registry.json.tasks[*].task_id` 中无匹配，必须 fail fast

## Skill Contract

`skills/vibe-task/SKILL.md` 必须满足：

- `name: vibe-task`
- `description` 以 `Use when...` 开头
- 明确触发词：
  - `vibe task`
  - `/vibe-task`
  - `哪个 worktree`
  - `任务总览`
  - `现在该进哪个 worktree`
- 工作流第一步必须运行 `bin/vibe task`
- 若 CLI 失败，skill 直接报告阻塞原因，不自行读取 registry
- 输出总结必须包含：
  - 当前 worktree 列表
  - 每个 worktree 的 task / status / next step / dirty
  - 推荐优先进入的 worktree

## Change Budget

以下是从“当前 WIP 快照”继续推进的预计剩余改动，不是从 `HEAD` 全新计算的理论总量：

| File | Type | Approx Remaining Change |
|------|------|--------------------------|
| `bin/vibe` | modify | `+0` 到 `+4` |
| `lib/task.sh` | modify | `+10` 到 `+35` |
| `skills/vibe-task/SKILL.md` | create | `+45` 到 `+90` |
| `tests/test_vibe.bats` | modify | `+0` 到 `+4` |
| `tests/test_task.bats` | modify | `+20` 到 `+60` |
| **Total** | 5 files | `~+75` 到 `+193` |

## Task 1: 锁定当前 CLI WIP 的真实基线

**Files:**
- Verify: `bin/vibe`
- Verify: `lib/task.sh`
- Verify: `tests/test_vibe.bats`
- Verify: `tests/test_task.bats`

**Step 1: 核对已有接线是否保留**

检查以下事实仍成立：

- `bin/vibe` 已包含 `task)` 分发
- `bin/vibe help` 已显示 `task`
- `lib/task.sh` 仍提供 `vibe_task()`
- `tests/test_task.bats` 已存在基本失败/成功用例

Run:

```bash
rg -n "task\\)|查看跨 worktree 的任务总览" bin/vibe
rg -n "vibe_task|Vibe Task Overview|Task not found in registry" lib/task.sh
rg -n "task command|vibe_task" tests/test_vibe.bats tests/test_task.bats
```

Expected:

- 命中现有 CLI WIP
- 不再按“从零新增 dispatcher/test file”理解此任务

**Step 2: 记录执行起点**

Run:

```bash
git status --short -- bin/vibe lib/task.sh tests/test_vibe.bats tests/test_task.bats
```

Expected:

- 明确哪些文件已 dirty / untracked
- 后续提交只聚焦这 4 个 CLI 相关文件，不混入其他脏文件

**Step 3: Commit policy**

这一任务本身只做基线确认，不提交。

## Task 2: 补齐 `vibe task` 缺失的失败分支与输出覆盖

**Files:**
- Modify: `lib/task.sh`
- Modify: `tests/test_task.bats`
- Modify: `tests/test_vibe.bats`（仅当 help 断言仍不够精确时）

**Step 1: 扩充 Bats 用例，先覆盖缺口**

在 `tests/test_task.bats` 基础上补至少 3 类用例：

1. 不在 git repo 时返回非零并报 `Not in a git repository`
2. `worktrees.json.current_task` 在 registry 中不存在时返回非零并报 `Task not found in registry`
3. `dirty=false` 时输出 `clean`

如当前 help 断言只检查包含 `task` 单词，可把 `tests/test_vibe.bats` 收紧到更具体文案，例如：

```bash
[[ "$output" =~ "查看跨 worktree 的任务总览" ]]
```

**Step 2: 先运行测试确认当前实现缺口**

Run:

```bash
bats tests/test_vibe.bats tests/test_task.bats
```

Expected:

- 新增覆盖点先失败，暴露当前实现缺口
- 失败原因应直接对应缺失分支，而不是测试夹具本身错误

**Step 3: 最小化补强 `lib/task.sh`**

只做为测试过关所必需的最小改动，优先保留现有结构：

- 继续使用 `vibe_require git jq`
- 保持 `_vibe_task_common_dir`, `_vibe_task_require_file`, `_vibe_task_missing_tasks`, `_vibe_task_render` 的职责分离
- 如需新增 helper，确保总行数仍 `<= 200`
- 不引入 JSON 输出或复杂参数解析

**Step 4: 回归测试**

Run:

```bash
bats tests/test_vibe.bats tests/test_task.bats
```

Expected:

- CLI 测试全部通过
- 输出仍保持 `Vibe Task Overview` 文本契约

**Step 5: Commit**

```bash
git add bin/vibe lib/task.sh tests/test_vibe.bats tests/test_task.bats
git commit -m "feat(vibe-task): harden cli overview reader"
```

## Task 3: 新增 `vibe-task` skill，强制走 CLI

**Files:**
- Create: `skills/vibe-task/SKILL.md`

**Step 1: 参考现有 skill 风格，但不要复制逻辑**

参考：

- `skills/vibe-check/SKILL.md`
- `skills/vibe-continue/SKILL.md`

要求：

- `name: vibe-task`
- `description` 以 `Use when...` 开头
- 增加 3 个以上 triggers，覆盖：
  - `vibe task`
  - `/vibe-task`
  - `哪个 worktree`
  - `任务总览`

**Step 2: 工作流第一步强制执行 CLI**

skill 必须写清楚：

```bash
bin/vibe task
```

且失败时直接报告，不得 fallback 到手动读 registry。

**Step 3: 输出结构**

skill 总结至少包含：

- Worktrees
- Current task
- Current subtask
- Next step
- State
- Recommendation

**Step 4: 文档检查**

Run:

```bash
rg -n "Use when|vibe task|/vibe-task|current task|next step|dirty|worktree" skills/vibe-task/SKILL.md
wc -l skills/vibe-task/SKILL.md
```

Expected:

- 触发词齐全
- 术语与现有共享 schema 保持一致
- 行数保持可控

**Step 5: Commit**

```bash
git add skills/vibe-task/SKILL.md
git commit -m "feat(vibe-task): add skill wrapper for task overview"
```

## Task 4: 统一验证 CLI 与 skill 边界

**Files:**
- Verify only

**Step 1: 运行测试集**

Run:

```bash
bats tests/test_vibe.bats tests/test_task.bats
```

Expected:

- 全部通过

**Step 2: 人工验证 CLI**

Run:

```bash
bin/vibe help
bin/vibe task
```

Expected:

- `help` 显示 `task`
- `vibe task` 输出 `Vibe Task Overview`
- 输出包含当前 registry 中的 worktree 和 task

**Step 3: 人工验证 skill**

复现实验步骤：

1. 在当前项目里触发 `vibe-task`
2. 观察 skill 是否先调用 `bin/vibe task`
3. 检查输出是否包含：
   - worktree 列表
   - task 状态
   - 推荐进入的 worktree

Expected:

- skill 不重复实现 registry 读取
- skill 只是解释 CLI 输出

**Step 4: 检查治理边界**

Run:

```bash
wc -l bin/vibe lib/*.sh
wc -l skills/vibe-task/SKILL.md
```

Expected:

- `bin + lib` 总行数仍 `<= 1200`
- `lib/task.sh` 行数 `<= 200`
- `skills/vibe-task/SKILL.md` 未失控膨胀

## Risks

### 风险 1: CLI 与 skill 各自维护一套逻辑

- **影响**：输出不一致，后续维护成本翻倍
- **对策**：skill 强制调用 `bin/vibe task`，禁止直接重复解析 registry
- **回滚条件**：若 skill 必须重写大量解析逻辑，停止实现，回到讨论阶段收缩职责

### 风险 2: 新增 skill 后触发语义和 CLI 混淆

- **影响**：用户不知道该用 `vibe task` 还是 `vibe-task`
- **对策**：在 skill 中明确 CLI 是底层事实入口，skill 是解释层
- **回滚条件**：如果命名冲突在真实使用中造成高混淆，再讨论是否改名

### 风险 3: `lib/task.sh` 实现过大

- **影响**：shell 文件膨胀，违反项目硬约束
- **对策**：V1 只做 overview，不加筛选、排序、JSON 输出
- **回滚条件**：若超出 `<= 200` 行，缩减输出字段，先保证最小总览可用

## Test Command

```bash
bats tests/test_vibe.bats tests/test_task.bats
bin/vibe help
bin/vibe task
rg -n "Use when|vibe task|/vibe-task|current task|next step|dirty|worktree" skills/vibe-task/SKILL.md
wc -l bin/vibe lib/*.sh
wc -l skills/vibe-task/SKILL.md
```

## Expected Result

- `vibe help` 显示 `task` 子命令。
- `vibe task` 能读取共享 registry 并输出跨 worktree 总览。
- 新增 `skills/vibe-task/SKILL.md`，其职责是解释 `vibe task` 的输出并给出建议。
- 命令与 skill 共用同一数据来源，不产生第二套解析实现。

## Change Summary

| File | Type | Approx Change |
|------|------|---------------|
| `bin/vibe` | modify | `+0` 到 `+4` |
| `lib/task.sh` | modify | `+10` 到 `+35` |
| `skills/vibe-task/SKILL.md` | create | `+45` 到 `+90` |
| `tests/test_vibe.bats` | modify | `+0` 到 `+4` |
| `tests/test_task.bats` | modify | `+20` 到 `+60` |
| **Total** | 5 files | `~+75` 到 `+193` |

## Execution Notes

- 这是一个统一语义的单逻辑变更：为跨 worktree 任务总览同时补齐 CLI 与 skill 两层入口。
- 执行时先落 CLI，再落 skill，避免 skill 先依赖一个不存在的底层命令。
- 若实现中发现必须修改共享 registry schema 或新增 `vibe-switch`，视为计划失效，停止执行并返回讨论阶段。
