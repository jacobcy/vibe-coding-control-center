# Vibe 3.0 Execution Plan (Isolated Phase Logic)

> **⚠️ Agent Instruction**: Focus ONLY on the current Phase. Do not attempt to optimize or understand the global roadmap. Your success is measured strictly by the Command-Line Acceptance Criteria below.

> **数据真源**: [docs/standards/v3/handoff-store-standard.md](../../standards/v3/handoff-store-standard.md)
> **GitHub 调用**: [docs/standards/v3/github-remote-call-standard.md](../../standards/v3/github-remote-call-standard.md)

---

## Technical Authority (Minimum Context)

- [Architecture Design](../implementation/02-architecture.md) ( Authority on File Layers)
- [Coding Standards](../implementation/03-coding-standards.md) (Authority on Linting/Types)
- [Data Standards](../../standards/v3/handoff-store-standard.md) (Authority on Database Schema)
- [GitHub Standards](../../standards/v3/github-remote-call-standard.md) (Authority on Remote Calls)

---

## Phase 0: Environment Ready

**Objective**: Verify the code playground and path accessibility.

**Inputs**: `ls -R lib3/ scripts/python/`
**Criteria**:
- [ ] Confirm `bin/vibe3` is executable and its path is correct.
- [ ] List the 5 layers defined in `02-architecture.md` to confirm file access.
- [ ] Run `bin/vibe3 --version` to check existing entry point.

---

## Phase 1: CLI Skeleton & Contract

**Objective**: Build or fix the shell-to-python dispatching layer.

**Inputs**: `docs/v3/plans/01-command-and-skeleton.md`
**Success Criteria**:
- [ ] `bin/vibe3 flow --help` returns zero exit code + domain usage.
- [ ] `bin/vibe3 task --help` returns zero exit code + domain usage.
- [ ] `bin/vibe3 pr --help` returns zero exit code + domain usage.
- [ ] `mypy scripts/python/vibe_core.py` returns no errors.

---

## Phase 2: Flow & Task State (SQLite)

**Objective**: Implement handoff store for Flow's three-phase process (plan/execute/review).

**Inputs**: `docs/v3/plans/02-flow-task-foundation.md`, `scripts/python/lib/store.py`
**Success Criteria**:
- [ ] Execution of `vibe3 flow new test-flow --task 101` creates handoff record in SQLite.
- [ ] `vibe3 flow status --json` output contains `"flow_slug": "test-flow"` with handoff metadata.
- [ ] Unit tests for `FlowManager` pass with 100% success rate.

---

## Phase 3: PR Domain (GitHub Integration)

**Objective**: Implement PR automation logic.

**Inputs**: `docs/v3/plans/03-pr-domain.md`
**Success Criteria**:
- [ ] `vibe3 pr draft` generates a PR URL (mocked or real) with valid metadata in body.
- [ ] `vibe3 pr ready` updates the PR labels/status via GitHub API helper.
- [ ] Log file shows "Metadata injected" entry for the current branch.

---

## Phase 4: Handoff & Logic Cutover

**Objective**: Bridge SQLite state to Markdown handoff files.

**Inputs**: `docs/v3/plans/04-handoff-and-cutover.md`
**Success Criteria**:
- [ ] `vibe3 handoff edit` successfully writes to `handoff.md`.
- [ ] `bin/vibe` (the existing v2 entry) correctly redirects to `vibe3` when configured.
- [ ] Comparison tool confirms SQL record matches Markdown state.

---

## Phase 5: Verification & Cleanup

**Objective**: Final performance and code quality sweep.

**Inputs**: `docs/v3/plans/05-polish-and-cleanup.md`
**Success Criteria**:
- [ ] `time bin/vibe3 flow status` reports execution time < 1.0s.
- [ ] No `TODO` comments or `print()` debugs remain in `scripts/python/`.
- [ ] All smoke tests in `tests3/` pass.

---

## Summary (Agent Budget)

| Phase | Core Input | Measurement |
|-------|------------|-------------|
| 0: Env | `02-architecture.md` | Path check |
| 1: Skeleton | `01-command-and-skeleton.md` | Help flags |
| 2: State | `02-flow-task-foundation.md` | SQL/JSON |
| 3: PR | `03-pr-domain.md` | API Log |
| 4: Sync | `04-handoff-and-cutover.md` | Handoff.md |
| 5: Final | `05-polish-and-cleanup.md` | Timing/Lint |

---

## Reviewer's Audit Guide (Phase 6)

**Objective**: Verify the integrity of the 5-layer architecture and the continuity of state between Executors.

### 1. Chain of Evidence Check
- [ ] Confirm that each Phase's Handoff section was correctly addressed by the subsequent Executor.
- [ ] Verify that `vibe3` commands are not "hallucinated" but actually implemented in `scripts/python/`.

### 2. Integration Verification
- [ ] Run `bin/vibe flow status` and confirm it uses the `vibe3` logic path.
- [ ] Check `scripts/python/lib/store.py` for generic type safety and SQL injection guards.

### 3. Consistency Check
- [ ] Cross-reference the current implementation with **[02-architecture.md](../implementation/02-architecture.md)**.

---
**Status**: Revised for Scope Isolation and Distributed Execution (2026-03-15)
**：19-26 小时（约 3-4 个工作日）

---

## 参考文档

### 业务计划文档（定义"做什么"）
- **[README.md](README.md)** - 总体进度看板
- **[01-command-and-skeleton.md](01-command-and-skeleton.md)** - Phase 1 业务目标
- **[02-flow-task-foundation.md](02-flow-task-foundation.md)** - Phase 2 业务目标
- **[03-pr-domain.md](03-pr-domain.md)** - Phase 3 业务目标
- **[04-handoff-and-cutover.md](04-handoff-and-cutover.md)** - Phase 4 业务目标
- **[05-polish-and-cleanup.md](05-polish-and-cleanup.md)** - Phase 5 业务目标

### 技术实施文档（定义"如何做"）
- **[../implementation/README.md](../implementation/README.md)** - 技术实施索引
- **[../implementation/02-architecture.md](../implementation/02-architecture.md)** - 架构设计 ⭐
- **[../implementation/03-coding-standards.md](../implementation/03-coding-standards.md)** - 编码标准 ⭐
- **[../implementation/05-logging.md](../implementation/05-logging.md)** - 日志系统
- **[../implementation/06-error-handling.md](../implementation/06-error-handling.md)** - 异常处理

### 项目标准
- **[../../../.agent/rules/python-standards.md](../../../.agent/rules/python-standards.md)** - Python 标准
- **[../../../SOUL.md](../../../SOUL.md)** - 项目宪法
- **[../../../CLAUDE.md](../../../CLAUDE.md)** - 项目上下文

---

**维护者**：Vibe Team
**最后更新**：2026-03-15