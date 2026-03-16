---
document_type: plan
title: Runtime Boundary Cleanup Plan
status: draft
author: GPT-5 Codex
created: 2026-03-11
last_updated: 2026-03-11
related_docs:
  - docs/standards/v2/data-model-standard.md
  - docs/standards/git-workflow-standard.md
  - docs/standards/worktree-lifecycle-standard.md
  - .agent/context/task.md
---

# Runtime Boundary Cleanup Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 收敛 runtime 主索引语义，减少 `worktree` 作为治理主语的使用，并把当前 flow/runtime 判断尽量拉回 `branch` 优先。

**Architecture:** 先在现有 shell 能力层中识别哪些读写路径把 `worktrees.json` 当成主判断入口，再以最小改动把查询、审计和 flow runtime 更新逻辑调整成 `branch-first`。历史态继续保留在 `flow-history.json`，不在本轮引入新的共享状态文件。

**Tech Stack:** Zsh, jq, bats, GitHub CLI

---

## Goal / Non-goals

**Goal**
- 降低 `vibe flow` / runtime 查询对 `worktree_name`、`worktree_path` 的主判断依赖
- 明确当前开放现场优先由 `branch` 锚定
- 保持 `flow-history.json` 继续承载已关闭 flow 历史

**Non-goals**
- 本轮不引入 `branches.json`
- 本轮不重构 `vibe task` / `vibe roadmap` 全部数据模型
- 本轮不处理所有历史脏数据修复，只保证新语义与关键路径行为一致

## Context

**需要读取的文件**
- `lib/flow_runtime.sh` - 当前 flow runtime 更新与 `switch` 语义
- `lib/flow.sh` - `new` / `done` 生命周期入口
- `lib/flow_show.sh` - flow 查询入口，验证 branch-first 展示
- `lib/flow_list.sh` - flow 列表与开放/关闭历史拼接
- `lib/task_actions.sh` - task runtime 绑定字段，确认不会和 flow runtime 语义冲突
- `lib/check_groups.sh` - runtime / link 检查口径
- `docs/standards/v2/data-model-standard.md` - 当前共享状态职责边界
- `tests/flow/test_flow_lifecycle.bats` - flow new/switch runtime 行为
- `tests/flow/test_flow_help_runtime.bats` - flow status/show/list 行为
- `tests/flow/test_flow_bind_done.bats` - flow done/history 收口行为

## Test Command

- `bats tests/flow/test_flow_lifecycle.bats`
- `bats tests/flow/test_flow_help_runtime.bats`
- `bats tests/flow/test_flow_bind_done.bats`
- `bin/vibe flow show --json`
- `bin/vibe flow list`

## Expected Result

- `vibe flow new/switch/show/list` 的关键判断与展示以 `branch` 为主
- `worktrees.json` 仍可作为开放现场容器，但不再承担历史归档语义
- `flow-history.json` 继续保留已关闭 flow 的 branch 历史
- 现有 flow 生命周期测试在调整后通过

## Tasks

### Task 1: 圈定 runtime 读写边界

**Files**
- Modify: `docs/standards/v2/data-model-standard.md`
- Modify: `docs/standards/worktree-lifecycle-standard.md`

**Steps**
1. 识别文档中仍把 `worktree` 写成 runtime 主语的段落
2. 明确本轮实现口径：开放态 branch-first，关闭态 history-first
3. 保持 `worktrees.json` 只表达当前开放现场，不承担历史判断

### Task 2: 调整 flow runtime 查询口径

**Files**
- Modify: `lib/flow_runtime.sh`
- Modify: `lib/flow_show.sh`
- Modify: `lib/flow_list.sh`
- Test: `tests/flow/test_flow_lifecycle.bats`
- Test: `tests/flow/test_flow_help_runtime.bats`

**Steps**
1. 写失败测试，覆盖 branch-first 查找与展示
2. 跑单测确认当前行为仍偏向 worktree 入口
3. 最小修改查询与更新逻辑，优先围绕 branch 解析当前 flow
4. 回跑测试确认通过

### Task 3: 校正 flow 收口与历史读取

**Files**
- Modify: `lib/flow.sh`
- Modify: `lib/flow_history.sh`
- Test: `tests/flow/test_flow_bind_done.bats`

**Steps**
1. 写失败测试，覆盖 flow done 后历史记录仍以 branch 回放
2. 检查 `_flow_history_close` 与 `_flow_history_show` 的 branch 匹配是否足够稳定
3. 只在必要处补强 branch-first 历史读取
4. 回跑相关测试

### Task 4: 校正审计口径

**Files**
- Modify: `lib/check_groups.sh`
- Modify: `lib/task_actions.sh` (仅当 runtime_branch 协同需要)
- Test: 相关 Bats 用例或新增最小回归测试

**Steps**
1. 确认哪些审计项把 worktree 缺失错误上升为主问题
2. 将可确定的 runtime 判断改成 branch-first
3. 保持 completed/archived task 清空 runtime 字段的现有约束不变

## Risks

### Risk 1: flow 查询结果回归
- **Impact:** `vibe flow show/list/status` 可能找不到当前 flow
- **Mitigation:** 先补 branch-first 失败测试，再改实现
- **Rollback:** 任一 flow 关键查询测试回退即停止本轮

### Risk 2: task runtime 与 flow runtime 语义冲突
- **Impact:** `bind-current` 或 `done` 后 shared state 不一致
- **Mitigation:** 修改前先核对 `runtime_branch` 与 `worktrees.json` 的现有联动
- **Rollback:** 若 `tests/flow/test_flow_bind_done.bats` 或 task runtime 用例回退，撤回相关实现

### Risk 3: 文档与实现口径不一致
- **Impact:** 后续 agent 继续误把 worktree 当治理主语
- **Mitigation:** 同步更新标准文档与帮助/测试断言
- **Rollback:** 若文档无法与当前实现保持一致，则缩小本轮实现范围

## Change Summary

- Files to modify: 7 到 9 个
- Expected line changes: 120 到 220 行
- 类型分布:
  - 代码: 60 到 120 行
  - 测试: 40 到 80 行
  - 文档: 20 到 40 行
