# Supervisor Periodic Audit Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 为仓库提供一套轻量周期性巡检能力，使治理检查可以同时在本地和 GitHub Actions 上运行，并统一产出 evidence-based report。

**Architecture:** 使用“声明式 check + 本地/远程共用 runner”的方案。check 真源位于 `.agent/governance/supervisors/*.yaml`；runner 负责加载 check、执行具体检查逻辑、输出统一 report；GitHub Actions 只负责 schedule 和发布结果。

**Tech Stack:** Python 3.10+, Typer, YAML, GitHub Actions, existing `check` / `review` / git utilities

---

## Why This Landing Point

Supervisor 的目标不是拦截 agent，而是定期审查仓库状态。因此最合适的实现是：

- repo 内提供可复跑的 CLI runner
- GitHub Actions 定时触发同一 runner

这样本地和远程共享同一套检查定义，不会出现两套标准。

---

## Target Files

### Create

- `src/vibe3/models/supervisor.py`
- `src/vibe3/services/supervisor_loader.py`
- `src/vibe3/services/supervisor_runner.py`
- `src/vibe3/services/supervisor_checks/__init__.py`
- `src/vibe3/services/supervisor_checks/github_pr_doc_backing.py`
- `src/vibe3/services/supervisor_checks/local_branch_cleanup.py`
- `src/vibe3/services/supervisor_checks/glossary_semantic_conflict.py`
- `tests/vibe3/services/test_supervisor_loader.py`
- `tests/vibe3/services/test_supervisor_runner.py`
- `.github/workflows/governance-audit.yml`

### Modify

- `src/vibe3/commands/check.py` or add a dedicated governance command group

### Existing Source of Truth

- `.agent/governance/supervisors/periodic-audit.yaml`
- `.agent/governance.yaml`
- `.agent/context/task.md`
- `docs/standards/glossary.md`

---

## Phase 1: Freeze the Check Schema

### Task 1: Model the narrow supervisor schema

**Files:**
- Modify: `.agent/governance/supervisors/periodic-audit.yaml`
- Create: `src/vibe3/models/supervisor.py`
- Test: `tests/vibe3/services/test_supervisor_loader.py`

**Intent:**
先把 check 的最小定义固定住，避免后续 runner 与 YAML 漂移。

**Required fields in v1:**
- `id`
- `enabled`
- `scope`
- `schedule`
- `target`
- `data_sources`
- `predicates`
- `on_violation`

**Step breakdown:**
1. 写 failing test，验证 YAML 能被加载
2. 建立 typed models
3. 实现 loader
4. 跑测试确认 schema 稳定

**Exit condition:**
当前 `periodic-audit.yaml` 可以被稳定解析。

---

## Phase 2: Build the Shared Runner

### Task 2: Implement a supervisor runner

**Files:**
- Create: `src/vibe3/services/supervisor_loader.py`
- Create: `src/vibe3/services/supervisor_runner.py`
- Test: `tests/vibe3/services/test_supervisor_runner.py`

**Intent:**
建立一个本地与远程共用的巡检执行器。

**Responsibilities:**
- 读取所有启用的 checks
- 分发到对应 check handler
- 汇总 report
- 返回适合 CLI / CI 的结果对象

**Step breakdown:**
1. 写 failing test，验证多个 check 可被 sequentially 执行
2. 实现 runner 的 registry / dispatch
3. 实现统一 report data model
4. 跑测试确认输出稳定

**Exit condition:**
runner 可以统一执行多个 check 并产出 report。

---

## Phase 3: Land the First Three Checks

### Task 3: Implement high-value narrow checks

**Files:**
- Create: `src/vibe3/services/supervisor_checks/github_pr_doc_backing.py`
- Create: `src/vibe3/services/supervisor_checks/local_branch_cleanup.py`
- Create: `src/vibe3/services/supervisor_checks/glossary_semantic_conflict.py`
- Test: `tests/vibe3/services/test_supervisor_runner.py`

**v1 checks:**
1. `github_pr_doc_backing`
2. `local_branch_cleanup`
3. `glossary_semantic_conflict`

**Why these first:**
- 覆盖远程、局部仓库状态、文档语义三类不同数据源
- 检查成本低
- 价值高且容易向用户解释

**Step breakdown:**
1. 为每条 check 写独立 fixture 和测试
2. 实现各自 handler
3. 把 handler 注册到 runner
4. 跑测试确认 evidence 输出完整

**Exit condition:**
至少 3 条 check 能在本地 runner 中运行并产出 report。

---

## Phase 4: Expose a Local CLI Entry

### Task 4: Add a local governance audit command

**Files:**
- Modify: `src/vibe3/commands/check.py` or add dedicated command module
- Modify: `src/vibe3/cli.py`
- Test: `tests/vibe3/commands/...`

**Intent:**
保证 GitHub Actions 调的不是一段孤立脚本，而是 repo 自己的正式 CLI 能力。

**Recommended shape:**
- `vibe check governance`
- or `vibe audit governance`

**Step breakdown:**
1. 选定命令归属
2. 接入 runner
3. 提供 `--json` 和人类可读输出
4. 补命令层测试

**Exit condition:**
本地可以通过正式 CLI 运行 supervisor。

---

## Phase 5: Add GitHub Scheduled Execution

### Task 5: Schedule the supervisor in GitHub Actions

**Files:**
- Create: `.github/workflows/governance-audit.yml`

**Intent:**
把本地 runner 复用到远程 schedule，形成真正的周期性巡检。

**Workflow responsibilities:**
- 定时触发
- 检出仓库
- 运行 governance CLI
- 保存 report artifact
- 可选：按 severity 创建 issue / comment

**Step breakdown:**
1. 写 workflow skeleton
2. 调用本地 CLI
3. 保存 report artifact
4. 在 failure / warning 情况下决定是否开 issue

**Exit condition:**
GitHub 每日可自动运行 supervisor。

---

## Phase 6: Unify the Report Contract

### Task 6: Standardize report output

**Files:**
- Modify: `src/vibe3/models/supervisor.py`
- Modify: `src/vibe3/services/supervisor_runner.py`
- Test: `tests/vibe3/services/test_supervisor_runner.py`

**Required fields:**
- `check_id`
- `status`
- `severity`
- `evidence`
- `message`
- `recommended_action`

**Intent:**
保证本地 CLI、artifact、issue/comment 使用同一套结果结构。

**Exit condition:**
report contract 在 CLI 和 CI 场景可复用。

---

## Validation Strategy

### Unit tests

- YAML schema load tests
- per-check handler tests
- runner aggregation tests
- report contract tests

### Integration checks

- CLI command can run all enabled checks
- GitHub workflow can run the same CLI entry
- report artifact contains evidence-rich output

---

## Risks and Constraints

### Constraint 1: Remote and local data sources differ

因此 checks 必须按 scope 区分，不要假定所有环境都有同样的数据。

### Constraint 2: Report-first, not auto-fix-first

第一版应以审查和暴露问题为主，不应急于自动修复。

### Constraint 3: Keep checks narrow

不要把“代码质量巡检”实现成一个巨大的模糊判断器，应以一组独立 check 组成。

---

## Deliverable of This Plan

完成后，仓库将拥有：

1. 可解析的 supervisor YAML schema
2. 一个本地与远程共用的 supervisor runner
3. 至少 3 条独立、可解释的周期性检查
4. 一个 GitHub Actions 定时巡检工作流
