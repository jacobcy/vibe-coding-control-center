---
document_type: plan
title: GH-157 Worktrees JSON Retirement Implementation Plan
status: proposed
author: GPT-5 Codex
created: 2026-03-13
last_updated: 2026-03-13
related_docs:
  - docs/plans/2026-03-13-gh-157-worktrees-json-retirement-plan.md
  - docs/plans/2026-03-13-gh-157-semantic-cleanup-prerequisite-plan.md
  - docs/plans/2026-03-13-gh-157-semantic-cleanup-expansion-plan.md
  - docs/standards/v3/data-model-standard.md
  - docs/standards/v3/command-standard.md
  - docs/standards/v3/registry-json-standard.md
related_issues:
  - gh-157
  - gh-152
---

# GH-157 Worktrees JSON Retirement Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 以最小破坏顺序把 `worktrees.json` 从 shell 主路径中移除，使 runtime 判断收敛到 `git 现场 + registry.json + flow-history.json`，并最终让新仓库初始化和主要查询/审计/closeout 路径不再依赖该文件。

**Architecture:** 采用 branch-first、registry-first 的收缩式迁移，而不是一次性删除。先去掉读路径硬依赖，再用“单个开放 branch 只允许一个 active focused task”的不变量替换 `worktrees.json.current_task`，随后移除写路径维护，最后清理 bootstrap/help/tests/docs 残留。这样可以避免在同一轮同时重写 query、closeout、audit 三套心智。

**Tech Stack:** Zsh, jq, Git, Bats, Markdown

---

## Goal / Non-goals

**Goal**
- `vibe flow status/show/pr`
- `vibe task list/audit/update`
- `vibe check`
- `vibe roadmap init`

以上路径在没有 `worktrees.json` 时仍能工作，或只给兼容期 warning。

**Non-goals**
- 本轮不新建 `branches.json`、`flows.json` 等替代共享状态文件
- 本轮不修改 roadmap remote-first 语义
- 本轮不引入第二套 focused task 持久化机制
- 本轮不重做全部历史 plans，只修当前实现与标准入口

## Design Decision

### 推荐方案：用“branch 上唯一 active task”替代 `current_task`

候选方案有三种：

1. 在 `registry.json` 新增 focused-task 专用字段
2. 继续保留 `worktrees.json.current_task` 直到最后再统一处理
3. 直接收敛为：单个开放 branch 同时只允许一个 active task，从 `registry.json.runtime_branch` 派生当前 focused task

推荐选项 3。

原因：

- 不需要再扩 schema
- 与 branch-first 语义一致
- 可以让 `flow show/status/pr`、`task list`、`flow done` 共享同一套推导逻辑

代价：

- 需要补一条新不变量：同一 branch 上若同时出现多个非终态 task，视为 runtime 异常并由 audit / show 明确报错，而不是靠 `worktrees.json.current_task` 硬选一个

## Task 1: 先去掉读路径对 `worktrees.json` 的硬依赖

**Files:**
- Modify: `lib/task_query.sh`
- Modify: `lib/flow_status.sh`
- Modify: `lib/flow_history.sh`
- Modify: `lib/check_groups.sh`
- Modify: `lib/task_audit.sh`
- Modify: `lib/task_audit_checks.sh`
- Test: `tests/flow/test_flow_help_runtime.bats`
- Test: `tests/task/test_task_count_by_branch.bats`
- Test: `tests/contracts/test_flow_contract.bats`
- Test: `tests/test_vibe.bats`

**Step 1: Write the failing tests**

- 新增或改造测试覆盖：
  - 缺失 `worktrees.json` 时 `vibe flow status --json` 仍可输出 branch-first 结果
  - 缺失 `worktrees.json` 时 `vibe task list --json` 仍可输出 task 列表
  - 缺失 `worktrees.json` 时 `vibe task audit` 与 `vibe check` 不再直接 fail-fast

**Step 2: Run test to verify it fails**

Run:

```bash
bats tests/flow/test_flow_help_runtime.bats tests/task/test_task_count_by_branch.bats tests/contracts/test_flow_contract.bats tests/test_vibe.bats
```

Expected:
- 现有实现因强依赖 `worktrees.json` 而失败

**Step 3: Write minimal implementation**

- `task_query` 改为：
  - branch 计数优先从 `registry.json.runtime_branch` 过滤
  - `worktrees.json` 缺失时不 return 1
- `flow_status` 改为：
  - 开放 flow 枚举优先从 registry runtime_branch 派生
  - `worktrees.json` 仅作可选路径/目录补充
- `check_groups` / `task_audit` 改为：
  - 缺失 `worktrees.json` 记 warning 或兼容提示
  - 不再把“文件不存在”本身视作 bootstrap / flow 失败

**Step 4: Run test to verify it passes**

Run:

```bash
bats tests/flow/test_flow_help_runtime.bats tests/task/test_task_count_by_branch.bats tests/contracts/test_flow_contract.bats tests/test_vibe.bats
```

Expected:
- 以上命令在无 `worktrees.json` 时通过

**Step 5: Commit**

```bash
git add lib/task_query.sh lib/flow_status.sh lib/flow_history.sh lib/check_groups.sh lib/task_audit.sh lib/task_audit_checks.sh tests/flow/test_flow_help_runtime.bats tests/task/test_task_count_by_branch.bats tests/contracts/test_flow_contract.bats tests/test_vibe.bats
git commit -m "refactor(runtime): remove worktrees read hard dependency"
```

## Task 2: 用 registry-first 不变量替换 `current_task`

**Files:**
- Modify: `lib/flow_show.sh`
- Modify: `lib/flow_pr.sh`
- Modify: `lib/flow_list.sh`
- Modify: `lib/flow_history.sh`
- Modify: `lib/task_query.sh`
- Modify: `lib/task_actions.sh`
- Test: `tests/flow/test_flow_help_runtime.bats`
- Test: `tests/flow/test_flow_pr_review.bats`
- Test: `tests/contracts/test_flow_contract.bats`
- Test: `tests/task/test_task_ops.bats`

**Step 1: Write the failing tests**

- 新增或改造测试覆盖：
  - 同一 `runtime_branch` 只有一个非终态 task 时，`flow show/status/pr` 正确识别当前 task
  - 同一 `runtime_branch` 存在多个非终态 task 时，返回明确异常，而不是隐式选一个
  - `flow done` 在没有 `worktrees.json.current_task` 时，仍能从 registry 推导 closeout 摘要

**Step 2: Run test to verify it fails**

Run:

```bash
bats tests/flow/test_flow_help_runtime.bats tests/flow/test_flow_pr_review.bats tests/contracts/test_flow_contract.bats tests/task/test_task_ops.bats
```

Expected:
- 现有实现仍依赖 `.current_task` / `.tasks[]`

**Step 3: Write minimal implementation**

- 抽一个统一 helper：
  - 输入 branch
  - 从 `registry.json` 找出该 branch 下非终态 tasks
  - 若数量为 1，返回 focused task
  - 若数量为 0，返回空
  - 若数量 > 1，返回可审计错误
- `flow_show` / `flow_pr` / `flow_list` / `flow_history` 全部改用该 helper
- `task_actions --bind-current` 若发现当前 branch 已有其它非终态 focused task，直接阻断或要求先解绑定

**Step 4: Run test to verify it passes**

Run:

```bash
bats tests/flow/test_flow_help_runtime.bats tests/flow/test_flow_pr_review.bats tests/contracts/test_flow_contract.bats tests/task/test_task_ops.bats
```

Expected:
- `current_task` 不再需要从 `worktrees.json` 推导
- 多 active task 同 branch 被清晰拒绝

**Step 5: Commit**

```bash
git add lib/flow_show.sh lib/flow_pr.sh lib/flow_list.sh lib/flow_history.sh lib/task_query.sh lib/task_actions.sh tests/flow/test_flow_help_runtime.bats tests/flow/test_flow_pr_review.bats tests/contracts/test_flow_contract.bats tests/task/test_task_ops.bats
git commit -m "refactor(runtime): derive focused task from registry"
```

## Task 3: 去掉写路径对 `worktrees.json` 的维护

**Files:**
- Modify: `lib/flow_runtime.sh`
- Modify: `lib/task_write.sh`
- Modify: `lib/task_actions.sh`
- Modify: `lib/flow_history.sh`
- Test: `tests/flow/test_flow_lifecycle.bats`
- Test: `tests/flow/test_flow_bind_done.bats`
- Test: `tests/task/test_task_ops.bats`

**Step 1: Write the failing tests**

- 新增或改造测试覆盖：
  - `vibe flow new/switch` 不再 upsert `worktrees.json`
  - `vibe task update --bind-current` 只维护 `registry.json.runtime_*`
  - `vibe flow done` 清 runtime 时不再清 `worktrees.json`

**Step 2: Run test to verify it fails**

Run:

```bash
bats tests/flow/test_flow_lifecycle.bats tests/flow/test_flow_bind_done.bats tests/task/test_task_ops.bats
```

Expected:
- 现有测试仍在断言写入 `worktrees.json`

**Step 3: Write minimal implementation**

- 删除或停用：
  - `_flow_update_current_worktree_branch` 主路径调用
  - `task_write` 对 `.worktrees[].current_task/.tasks/.branch` 的同步
  - `flow_history` closeout 时对 `worktrees.json` 的清空联动
- 保留：
  - `runtime_worktree_name/path` 写入 `registry.json`
  - `flow-history.json` 的 closeout 摘要

**Step 4: Run test to verify it passes**

Run:

```bash
bats tests/flow/test_flow_lifecycle.bats tests/flow/test_flow_bind_done.bats tests/task/test_task_ops.bats
```

Expected:
- shell 主路径已不再写 `worktrees.json`

**Step 5: Commit**

```bash
git add lib/flow_runtime.sh lib/task_write.sh lib/task_actions.sh lib/flow_history.sh tests/flow/test_flow_lifecycle.bats tests/flow/test_flow_bind_done.bats tests/task/test_task_ops.bats
git commit -m "refactor(runtime): stop maintaining worktrees state"
```

## Task 4: 去掉 bootstrap、help、安装与契约测试前提

**Files:**
- Modify: `lib/roadmap_init.sh`
- Modify: `lib/task_help.sh`
- Modify: `tests/roadmap/test_roadmap_write_audit.bats`
- Modify: `tests/test_install.bats`
- Modify: `tests/contracts/test_shared_state_contracts.bats`
- Modify: `tests/contracts/test_github_project_bootstrap.bats`
- Modify: `tests/helpers/flow_common.bash`
- Modify: `docs/standards/v3/data-model-standard.md`
- Modify: `docs/standards/v3/command-standard.md`

**Step 1: Write the failing tests**

- 新增或改造测试覆盖：
  - `vibe roadmap init` 不再创建 `worktrees.json`
  - 安装与 shared-state 合同测试不再把 `worktrees.json` 视为必需骨架
  - task audit help 不再出现 `--fix-branches`

**Step 2: Run test to verify it fails**

Run:

```bash
bats tests/roadmap/test_roadmap_write_audit.bats tests/test_install.bats tests/contracts/test_shared_state_contracts.bats tests/contracts/test_github_project_bootstrap.bats
```

Expected:
- 现有测试仍预期 `worktrees.json` 存在

**Step 3: Write minimal implementation**

- `roadmap_init` 停止创建 `worktrees.json`
- `task_help` 删除修复旧字段文案
- 合同测试改为：
  - shared-state 最小骨架 = `registry.json` + `roadmap.json` + `flow-history.json`
  - `worktrees.json` 若存在，也只是兼容遗留，不再是标准前提

**Step 4: Run test to verify it passes**

Run:

```bash
bats tests/roadmap/test_roadmap_write_audit.bats tests/test_install.bats tests/contracts/test_shared_state_contracts.bats tests/contracts/test_github_project_bootstrap.bats
```

Expected:
- 初始化与合同测试已不再依赖 `worktrees.json`

**Step 5: Commit**

```bash
git add lib/roadmap_init.sh lib/task_help.sh tests/roadmap/test_roadmap_write_audit.bats tests/test_install.bats tests/contracts/test_shared_state_contracts.bats tests/contracts/test_github_project_bootstrap.bats tests/helpers/flow_common.bash docs/standards/v3/data-model-standard.md docs/standards/v3/command-standard.md
git commit -m "refactor(runtime): remove worktrees bootstrap contract"
```

## Task 5: 全量回归并产出收尾审计

**Files:**
- Create: `docs/plans/2026-03-13-gh-157-worktrees-json-retirement-audit-report.md`
- Review: `lib/**/*.sh`
- Review: `tests/**/*.bats`
- Review: `docs/standards/**/*.md`

**Step 1: Run targeted verification**

Run:

```bash
bats tests/flow/test_flow_help_runtime.bats tests/flow/test_flow_pr_review.bats tests/flow/test_flow_lifecycle.bats tests/flow/test_flow_bind_done.bats tests/task/test_task_count_by_branch.bats tests/task/test_task_ops.bats tests/contracts/test_flow_contract.bats tests/contracts/test_shared_state_contracts.bats tests/contracts/test_github_project_bootstrap.bats tests/roadmap/test_roadmap_write_audit.bats tests/test_install.bats tests/test_vibe.bats
```

Expected:
- 关键 runtime/query/audit/bootstrap 路径通过

**Step 2: Run repo verification**

Run:

```bash
bash scripts/hooks/lint.sh
rg -n "worktrees\\.json" lib tests docs/standards docs/plans
rg -n "current_task|\\.tasks\\[|runtime_branch|runtime_worktree_name" lib tests
```

Expected:
- `worktrees.json` 命中只剩历史说明、迁移说明或专门审计报告
- `current_task` 不再来自 `worktrees.json`

**Step 3: Write audit report**

- 记录：
  - 还剩哪些 `worktrees.json` 命中
  - 是否全为历史文档或兼容说明
  - 是否还有 follow-up

**Step 4: Commit**

```bash
git add docs/plans/2026-03-13-gh-157-worktrees-json-retirement-audit-report.md
git commit -m "docs(runtime): audit worktrees retirement residuals"
```

## Risks

### Risk 1: branch 上多 active task 的老数据触发新不变量
- **Impact:** 现有仓库在切换到 registry-first focused task 后直接报异常
- **Mitigation:** 在 Task 2 里先把它做成显式审计错误，并在必要时补一个一次性修复脚本或迁移步骤

### Risk 2: `flow done` closeout 摘要丢失当前 task 信息
- **Impact:** `flow-history.json` 会缺少过去依赖 `current_task` 的信息
- **Mitigation:** 先让 `flow_history` 从 `runtime_branch` 反查 registry，并用测试覆盖“无 worktrees 仍可 closeout”

### Risk 3: 初始化契约改动牵动大量旧测试夹具
- **Impact:** 测试面会在最后一段集中爆炸
- **Mitigation:** 不把 bootstrap 改动提前；等读写主路径稳定后再统一改测试契约

## Execution Handoff

Plan complete and saved to `docs/plans/2026-03-13-gh-157-worktrees-json-retirement-implementation-plan.md`. Two execution options:

1. Subagent-Driven (this session) - I dispatch fresh subagent per task, review between tasks, fast iteration

2. Parallel Session (separate) - Open new session with executing-plans, batch execution with checkpoints

Which approach?
