---
document_type: index
title: Vibe 3.0 Execution Plan
status: active
author: Claude Sonnet 4.6
created: 2026-03-15
last_updated: 2026-03-17
related_docs:
  - docs/v3/handoff/v3-rewrite-plan.md
  - docs/v3/infrastructure/02-architecture.md
  - docs/v3/infrastructure/03-coding-standards.md
  - docs/v3/infrastructure/04-test-standards.md
  - docs/standards/v3/handoff-store-standard.md
  - docs/standards/v3/github-remote-call-standard.md
---

# Vibe 3.0 Execution Plan (Isolated Phase Logic)

> **⚠️ Agent Instruction**: Focus ONLY on the current Phase. Do not attempt to optimize or understand the global roadmap. Your success is measured strictly by the Command-Line Acceptance Criteria below.

> **数据真源**: [docs/standards/v3/handoff-store-standard.md](../../standards/v3/handoff-store-standard.md)
> **GitHub 调用**: [docs/standards/v3/github-remote-call-standard.md](../../standards/v3/github-remote-call-standard.md)

---

## Technical Authority (Minimum Context)

- [Architecture Design](../infrastructure/02-architecture.md) (Authority on File Layers)
- [Coding Standards](../infrastructure/03-coding-standards.md) (Authority on Linting/Types)
- [Data Standards](../../standards/v3/handoff-store-standard.md) (Authority on Database Schema)
- [GitHub Standards](../../standards/v3/github-remote-call-standard.md) (Authority on Remote Calls)

---

## Phase 01: CLI Skeleton & Contract

**Objective**: Establish the `vibe3` entry point and the dispatching logic to domain managers.

**Inputs**: `docs/v3/handoff/01-command-and-skeleton.md`
**Success Criteria**:
- [ ] `bin/vibe3 flow --help` returns zero exit code + domain usage.
- [ ] `bin/vibe3 task --help` returns zero exit code + domain usage.
- [ ] `bin/vibe3 pr --help` returns zero exit code + domain usage.
- [ ] `mypy src/vibe3/ --strict` returns no errors.

---

## Phase 02: Flow & Task State (SQLite)

**Objective**: Implement handoff store for Flow's three-phase process (plan/execute/review).

**Inputs**: `docs/v3/handoff/02-flow-task-foundation.md`, `src/vibe3/clients/sqlite_client.py`
**Success Criteria**:
- [ ] Execution of `vibe3 flow new test-flow --task 101` creates handoff record in SQLite.
- [ ] `vibe3 flow status --json` output contains `"flow_slug": "test-flow"` with handoff metadata.
- [ ] Unit tests for `FlowService` pass with 100% success rate.

---

## Phase 03: PR Domain (GitHub Integration)

**Objective**: Implement PR automation logic.

**Inputs**: `docs/v3/handoff/03-pr-domain.md`
**Success Criteria**:
- [ ] `vibe3 pr draft` generates a PR URL (mocked or real) with valid metadata in body.
- [ ] `vibe3 pr ready` updates the PR labels/status via GitHub API helper.
- [ ] Log file shows "Metadata injected" entry for the current branch.

---

## Phase 04: Handoff & Logic Cutover

**Objective**: Bridge SQLite state to Markdown handoff files.

**Inputs**: `docs/v3/handoff/04-handoff-and-cutover.md`
**Success Criteria**:
- [ ] `vibe3 handoff sync` successfully writes to `handoff.md`.
- [ ] `bin/vibe` (the existing v2 entry) correctly redirects to `vibe3` when configured.
- [ ] Comparison tool confirms SQL record matches Markdown state.

---

## Phase 05: Verification & Cleanup

**Objective**: Final performance and code quality sweep.

**Inputs**: `docs/v3/handoff/05-polish-and-cleanup.md`
**Success Criteria**:
- [ ] `time bin/vibe3 flow status` reports execution time < 1.0s.
- [ ] No `TODO` comments or `print()` debugs remain in `src/`.
- [ ] All smoke tests in `tests3/` pass.

---

## Summary (Agent Budget)

| Phase | Core Input | Measurement |
|-------|------------|-------------|
| 01: Skeleton | `01-command-and-skeleton.md` | Help flags |
| 02: State | `02-flow-task-foundation.md` | SQL/JSON |
| 03: PR | `03-pr-domain.md` | API Log |
| 04: Sync | `04-handoff-and-cutover.md` | Handoff.md |
| 05: Final | `05-polish-and-cleanup.md` | Timing/Lint |

---

## Reviewer's Audit Guide (Phase 06)

**Objective**: Verify the integrity of the 5-layer architecture and the continuity of state between Executors.

### 1. Chain of Evidence Check
- [ ] Confirm that each Phase's Handoff section was correctly addressed by the subsequent Executor.
- [ ] Verify that `vibe3` commands are not "hallucinated" but actually implemented in `src/`.

### 2. Integration Verification
- [ ] Run `bin/vibe flow status` and confirm it uses the `vibe3` logic path.
- [ ] Check `src/vibe3/clients/sqlite_client.py` for generic type safety and SQL injection guards.

### 3. Consistency Check
- [ ] Cross-reference the current implementation with **[02-architecture.md](../infrastructure/02-architecture.md)**.

---

**Status**: Revised for Scope Isolation and Distributed Execution (2026-03-15)
**预估时间**: 19-26 小时(约 3-4 个工作日)

---

## 参考文档

### 执行计划文档
- **[v3-rewrite-plan.md](v3-rewrite-plan.md)** - 总体进度看板
- **[01-command-and-skeleton.md](01-command-and-skeleton.md)** - Phase 01 执行目标
- **[02-flow-task-foundation.md](02-flow-task-foundation.md)** - Phase 02 执行目标
- **[03-pr-domain.md](03-pr-domain.md)** - Phase 03 执行目标
- **[04-handoff-and-cutover.md](04-handoff-and-cutover.md)** - Phase 04 执行目标
- **[05-polish-and-cleanup.md](05-polish-and-cleanup.md)** - Phase 05 执行目标

### 技术权威文档
- **[../infrastructure/README.md](../infrastructure/README.md)** - 技术实施索引
- **[../infrastructure/02-architecture.md](../infrastructure/02-architecture.md)** - 架构设计 ⭐
- **[../infrastructure/03-coding-standards.md](../infrastructure/03-coding-standards.md)** - 编码标准 ⭐
- **[../infrastructure/04-test-standards.md](../infrastructure/04-test-standards.md)** - 测试标准 ⭐
- **[../infrastructure/05-logging.md](../infrastructure/05-logging.md)** - 日志系统
- **[../infrastructure/06-error-handling.md](../infrastructure/06-error-handling.md)** - 异常处理

### 项目标准
- **[../../standards/v3/handoff-store-standard.md](../../standards/v3/handoff-store-standard.md)** - 数据库标准 ⭐
- **[../../standards/v3/github-remote-call-standard.md](../../standards/v3/github-remote-call-standard.md)** - GitHub 调用标准 ⭐
- **[../../../.agent/rules/python-standards.md](../../../.agent/rules/python-standards.md)** - Python 标准
- **[../../../SOUL.md](../../../SOUL.md)** - 项目宪法
- **[../../../CLAUDE.md](../../../CLAUDE.md)** - 项目上下文

---

**维护者**: Vibe Team
**最后更新**: 2026-03-17