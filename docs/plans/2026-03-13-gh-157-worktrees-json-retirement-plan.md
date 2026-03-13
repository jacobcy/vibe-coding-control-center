---
document_type: plan
title: GH-157 Worktrees JSON Retirement Plan
status: proposed
author: GPT-5 Codex
created: 2026-03-13
last_updated: 2026-03-13
related_docs:
  - docs/plans/2026-03-13-gh-157-semantic-cleanup-prerequisite-plan.md
  - docs/plans/2026-03-13-gh-157-remote-first-roadmap-governance-plan.md
  - docs/standards/data-model-standard.md
  - docs/standards/command-standard.md
  - docs/standards/registry-json-standard.md
related_issues:
  - gh-157
  - gh-152
---

# GH-157 `worktrees.json` 清退计划

**Goal:** 把 `worktrees.json` 从共享状态主模型中清退，收敛到 `git 现场 + registry.json + flow-history.json` 的 branch-first 运行时语义，同时给兼容期保留明确边界。

**Architecture:** 先移除读取路径对 `worktrees.json` 的硬依赖，再移除写入路径对 `current_task/tasks/status/branch` 的持续维护，最后才撤掉 bootstrap、help 和测试夹具中的存在性前提。兼容期内允许保留空壳文件或只读 audit hint，但禁止再给它新增主模型职责。

**Tech Stack:** Zsh, jq, Bats, Git

---

## Goal / Non-goals

**Goal**
- 列清楚哪些命令仍直接读取或写入 `worktrees.json`
- 区分“兼容期暂时必需”与“可直接移除的历史残留”
- 明确清退后的 runtime 真相来源
- 给 GH-157 后续实现提供分阶段切换边界

**Non-goals**
- 本计划不直接改 shell 实现
- 本计划不立即删除 `worktrees.json`
- 本计划不在本轮发明新的长期 worktree 主模型
- 本计划不绕过现有 `registry.json` / `flow-history.json` 去创建另一份 branch registry

## Decision Baseline

- 开放 flow 的身份锚点是 `branch`，不是 `worktree`
- `worktree` 只表示 Git 物理目录；它的存在、路径、dirty 状态应优先从 Git 现场读取
- task runtime 绑定事实以 `registry.json` 为主
- 已关闭 flow 的历史事实以 `flow-history.json` 为主
- `worktrees.json` 在兼容期内最多只保留为 cache / audit hint，不能再承担开放 flow 的主身份或主索引

## Current Dependency Inventory

### P0: 仍在直接写入 `worktrees.json` 的运行时入口

- `lib/flow_runtime.sh`
  - `_flow_update_current_worktree_branch` 在 `vibe flow new/switch` 后 upsert 当前 worktree 条目
  - 仍维护 `.branch`、`.current_task`、`.tasks`、`.status`
- `lib/task_actions.sh`
  - `vibe task update --bind-current` 仍同步 `current_task` 与 worktree 绑定
  - task bind/unassign 仍要求 `worktrees.json` 存在
- `lib/flow_history.sh`
  - `_flow_close_branch_runtime` 在 `vibe flow done` 时清空匹配 branch 的 worktree runtime 字段
- `lib/roadmap_init.sh`
  - `vibe roadmap init` 仍创建 `worktrees.json` 作为共享状态骨架的一部分

### P0: 仍在直接读取 `worktrees.json` 做运行时判断的查询入口

- `lib/task_query.sh`
  - `_vibe_task_count_by_branch` 仍从 `.worktrees[].tasks[]` 计数，再与 `registry.json.runtime_branch` 合并
  - `_vibe_task_list` 仍把 `worktrees.json` 视为必需文件
  - 当前 worktree 的 focused task 仍优先来自 `.worktrees[].current_task`
- `lib/flow_status.sh`
  - `_flow_open_dashboard_json` 仍从 `.worktrees[].branch` 枚举开放 flow，再与 `registry.json.runtime_branch` 去重
- `lib/flow_history.sh`
  - `_flow_branch_dashboard_entry` 仍优先从 `worktrees.json` 读取 `current_task`、`tasks[]`、`worktree_path`

### P1: 审计/修复路径仍把 `worktrees.json` 当必备输入

- `lib/check_groups.sh`
  - `flow` 组直接校验 `worktrees.json` 的 persisted status
  - `bootstrap` 组把缺失 `worktrees.json` 判为失败
  - `link` 组用 `.worktrees[].worktree_name` 验证 task runtime 指向的 worktree 是否存在
- `lib/task_audit.sh`
  - `vibe task audit` 入口仍硬性要求 `worktrees.json` 存在
- `lib/task_audit_checks.sh`
  - branch registration 检查仍从 `.worktrees[].branch` 枚举开放现场
- `lib/task_help.sh`
  - help 文案仍暴露 “修复 worktrees.json 中的 null branch 字段” 这类旧职责

### P2: 测试夹具和断言仍深度耦合兼容字段

- `tests/flow/test_flow_lifecycle.bats`
  - 断言 `_flow_update_current_worktree_branch` 会 upsert `worktrees.json`
- `tests/flow/test_flow_bind_done.bats`
  - 断言 bind/done 会维护或清空 `.tasks[]`、`.current_task`、`.branch`
- `tests/flow/test_flow_help_runtime.bats`
  - 断言 `_flow_show/_flow_status` 可从 `worktrees.json` 读取当前 task
- `tests/task/test_task_ops.bats`
  - 断言 `--bind-current` 会把 `current_task` 写入 `worktrees.json`
- `tests/task/test_task_count_by_branch.bats`
  - 仍把 `.worktrees[].tasks[]` 当成 branch task 计数来源

## What Is Still Necessary vs. Removable

### 兼容期内暂时必需

- `roadmap init` 创建空壳 `worktrees.json`
  - 理由：当前多个 shell 命令仍把“文件存在”当启动前提
- `task_actions` / `flow_runtime` / `flow_history` 的写路径
  - 理由：现有 query / audit / tests 还在消费这些字段
- `flow_status` / `task_query` 的 fallback 读取
  - 理由：当前 `current_task` 焦点选择尚未完全迁走

### 可以直接列为历史残留并准备移除

- `worktrees.json.status`
  - 可被 Git 现场可达性 + registry/task 状态替代，不应继续做持久化真源
- `worktrees.json.tasks[]`
  - 与 `registry.json` 的 `runtime_branch/runtime_worktree_name` 重复
- `worktrees.json.current_task`
  - 是最关键但也最应该被替换的兼容字段，不应长期留在文件里
- `vibe task audit --fix-branches` 这类专门修 `worktrees.json` 的帮助口径
  - 属于历史修复工具语义，不应继续当成标准职责

## Retirement Boundary

### 清退后改由现场直接读取的事实

- 当前 worktree 根目录：`git rev-parse --show-toplevel`
- 当前 branch：`git branch --show-current`
- worktree 是否存在 / 是否主仓：Git / git-worktree 现场判断
- dirty 状态：`git status --porcelain`

### 清退后改由 `registry.json` 承担的事实

- task 与当前 branch 的绑定：`runtime_branch`
- task 与当前 worktree 的绑定：`runtime_worktree_name` / `runtime_worktree_path`
- task 与 agent 的当前运行时绑定：`runtime_agent`
- 当前开放 task 列表：按 `runtime_branch` 和非终态 status 过滤

### 清退后改由 `flow-history.json` 承担的事实

- 已关闭 flow 的 branch 历史
- closeout 时刻的摘要信息
- 不再依赖 `worktrees.json` 回放历史关闭态

## Main Blocker Before Deletion

`worktrees.json.current_task` 目前仍承载“同一 branch / 同一 worktree 下哪个 task 是当前焦点”的语义；仅靠 `runtime_branch` 还不能无损替代。

删除 `worktrees.json` 之前，必须先完成以下二选一之一：

1. 明确并强制“单个开放 branch/worktree 同时只允许一个 active focused task”的不变量，然后把 focused task 直接从 `registry.json` 过滤得出。
2. 在 `registry.json` 内引入一个明确、可审计、非重复的 focused-task 表达方式，替代 `current_task`。

在这个 blocker 没解决前，只能把 `current_task` 当兼容字段逐步收缩，不能直接删。

## Compatibility Strategy

- 兼容期允许保留 `worktrees.json` 文件本身，但应逐步收缩为：
  - 可为空数组
  - 不要求完整 `.tasks[]/.current_task/.status` 语义
  - 缺失时 query/audit 不应一律 fail-fast
- 新增实现禁止：
  - 再往 `worktrees.json` 增加新字段
  - 再把 branch/worktree 身份判断写回 `worktrees.json` 作为主路径
  - 再新增只为修复 `worktrees.json` 而存在的独立命令语义

## Phase Plan

### Phase 1: 去掉读路径硬依赖

**Files**
- `lib/task_query.sh`
- `lib/flow_status.sh`
- `lib/flow_history.sh`
- `lib/check_groups.sh`
- `lib/task_audit.sh`
- `lib/task_audit_checks.sh`

**Steps**
1. 让 query/audit 在 `worktrees.json` 缺失时仍能基于 `git + registry + flow-history` 输出结果
2. 把 branch 枚举与 runtime task 枚举统一迁到 `registry.json.runtime_branch`
3. 把“missing worktrees.json = fail” 改成兼容期 warning 或仅对旧命令给出迁移提示

**Exit**
- `vibe flow status`
- `vibe task list`
- `vibe task audit`
- `vibe check`
  
以上命令在无 `worktrees.json` 或空 `worktrees.json` 下仍可运行

### Phase 2: 替换 focused task 语义

**Files**
- `lib/task_query.sh`
- `lib/task_actions.sh`
- `lib/flow_history.sh`
- 相关 `tests/flow/*.bats`
- 相关 `tests/task/*.bats`

**Steps**
1. 选定 `current_task` 的替代方案
2. 把当前 focused task 选择从 `worktrees.json.current_task` 迁走
3. 停止依赖 `.tasks[]` 维护 branch 下 task 列表

**Exit**
- `current_task` 不再是 query 主路径
- `.tasks[]` 不再是 branch task 集合真源

### Phase 3: 去掉写路径维护

**Files**
- `lib/flow_runtime.sh`
- `lib/task_actions.sh`
- `lib/flow_history.sh`

**Steps**
1. 去掉 `new/switch/bind/done` 对 `worktrees.json` 的写入联动
2. closeout 清理只更新 `registry.json` 与 `flow-history.json`
3. 仅在必要时保留空壳文件，不再维护 branch/current_task/status

**Exit**
- 运行时 shell 主路径不再写 `worktrees.json`

### Phase 4: 去掉 bootstrap/help/test 前提

**Files**
- `lib/roadmap_init.sh`
- `lib/task_help.sh`
- `tests/flow/*.bats`
- `tests/task/*.bats`
- 相关 docs/plans / docs/standards

**Steps**
1. 停止把 `worktrees.json` 作为 shared-state skeleton 必备文件
2. 删除修复旧字段的 help 文案
3. 把测试夹具改成 registry-first / branch-first

**Exit**
- 新仓库初始化不再创建 `worktrees.json`
- 文档与测试不再把它写成标准前提

## Verification Commands

```bash
rg -n "worktrees\\.json" lib tests docs/standards docs/plans
```

**Expected**
- 每一次 phase 收口后，命中应只剩兼容说明或明确标注的迁移残留

```bash
rg -n "current_task|\\.tasks\\[|runtime_worktree_name|runtime_branch" lib/task_query.sh lib/flow_runtime.sh lib/check_groups.sh tests/flow tests/task
```

**Expected**
- 能明确区分哪些语义已迁到 registry，哪些仍是兼容 blocker

## Risks

### Risk 1: 过早删除 `current_task` 导致 flow/task UI 失焦
- **Impact:** `vibe flow status/show` 与 `vibe task list` 可能无法判断当前焦点 task
- **Mitigation:** 先替换 focused-task 语义，再删兼容字段

### Risk 2: 审计命令失去对 runtime 漂移的观测能力
- **Impact:** `vibe check` / `vibe task audit` 可能从“过度依赖 worktrees”直接变成“完全看不到 runtime 漂移”
- **Mitigation:** 把检查改写成 `git 现场 + registry + flow-history` 联合判断，而不是直接删除检查

### Risk 3: 兼容期无限拖长
- **Impact:** `worktrees.json` 名义上降级，实际上继续被新代码依赖
- **Mitigation:** 从本计划起，任何新增实现若再写入该文件，视为违反前置条件

## Exit Criteria

- 已有一份带优先级的 repo 级残留依赖清单
- `current_task` 替代方案被明确列为删除前 blocker
- 兼容期边界写清楚：允许保留文件，但不允许新增主模型职责
- GH-157 主计划可以把 `worktrees.json` 清退当成独立 phase，而不是边实现边猜
