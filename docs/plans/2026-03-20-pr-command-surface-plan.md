# PR Command Surface Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Status:** COMPLETED (2026-03-20)

**Goal:** 收敛 `vibe3 pr` 命令面，只保留 `create --draft`、`ready`、`show` 三个公开入口，并移除公开 `review-gate`。

**Architecture:** 本次不重写 `task / flow / review` 主链，只做命令面治理与内部入口下沉。公开 CLI 只保留有项目包装价值的 `pr` 命令；hook/CI 的 gate 改走内部 Python 入口，避免污染用户命令体系。

**Tech Stack:** Typer CLI、Python services、pytest、Git hooks、GitHub client。

---

## Implementation Summary

### Completed Tasks

| Task | Description | Status |
|------|-------------|--------|
| Task 1 | Freeze the target command contract | DONE |
| Task 2 | Replace `pr draft` with `pr create --draft` | DONE |
| Task 3 | Remove `pr merge` from public CLI | DONE |
| Task 4 | Move review gate behind an internal entry | DONE |
| Task 5 | Tighten `pr show` as the only PR query surface | DONE |
| Task 6 | Update design docs and handoff | DONE |
| Task 7 | Final verification | DONE |

### Key Changes

1. **PR Command Surface**:
   - `pr create --draft` - Create draft PR (replaces `pr draft`)
   - `pr ready` - Mark PR as ready with quality gates
   - `pr show` - Show PR details with change analysis

2. **Removed from Public CLI**:
   - `pr draft` - Now `pr create --draft`
   - `pr merge` - Merge handled by flow done / integrate
   - `pr version-bump` - No clear project packaging value
   - `review-gate` - Internal entry only

3. **Internal Entry Points**:
   - `python -m vibe3.commands.review_gate --check-block` - Pre-push hook

### Test Coverage

- 32 tests pass for PR command surface
- All type checks pass (`mypy src/vibe3`)
- Shell contract tests updated for internal entry

---

### Task 1: Freeze the target command contract

**Files:**
- Modify: `src/vibe3/commands/pr.py`
- Modify: `src/vibe3/cli.py`
- Test: `tests/vibe3/commands/test_pr_help.py` or corresponding PR help tests
- Test: `tests/vibe3/integration/test_review_shell_contract.py`

**Step 1: Write the failing command-surface tests**

新增或更新测试，明确以下契约：

- `vibe3 pr --help` 只显示 `create`、`ready`、`show`
- 不再显示 `draft`
- 不再显示 `merge`
- 顶层 help 不再显示 `review-gate`

**Step 2: Run tests to verify the gap**

Run: `uv run pytest tests/vibe3/commands/test_pr_help.py tests/vibe3/integration/test_review_shell_contract.py -v`

Expected: FAIL，直到旧命令面被收敛。

**Step 3: Remove stale public command registrations**

- 从 `src/vibe3/commands/pr.py` 移除 `draft` 注册方式
- 从 `src/vibe3/cli.py` 移除顶层 `review-gate` 注册
- 删除 `merge` 的公开注册

**Step 4: Run focused tests**

Run: `uv run pytest tests/vibe3/commands/test_pr_help.py tests/vibe3/integration/test_review_shell_contract.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add src/vibe3/commands/pr.py src/vibe3/cli.py tests/vibe3/commands/test_pr_help.py tests/vibe3/integration/test_review_shell_contract.py
git commit -m "refactor(pr): simplify public command surface"
```

### Task 2: Replace `pr draft` with `pr create --draft`

**Files:**
- Modify: `src/vibe3/commands/pr_create.py`
- Modify: `src/vibe3/services/pr_service.py`
- Test: `tests/vibe3/commands/test_pr_create.py`

**Step 1: Write the failing tests**

覆盖：

- `vibe3 pr create --draft` 创建 draft PR
- `vibe3 pr create` 默认行为是否仍为 draft，必须显式定下来
- `vibe3 pr draft` 不再存在

推荐默认：

- `create` 要求显式 `--draft`
- 如果未来需要非 draft create，再单独扩展

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/vibe3/commands/test_pr_create.py -v`

Expected: FAIL

**Step 3: Implement minimal command reshaping**

- 将 `draft()` 重命名/迁移为 `create()`
- `--draft` 成为 create 的显式选项
- 继续复用现有 `PRService.create_draft_pr()`，不要顺手扩张非 draft 创建逻辑

**Step 4: Run focused tests**

Run: `uv run pytest tests/vibe3/commands/test_pr_create.py tests/vibe3/commands/test_pr_help.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add src/vibe3/commands/pr_create.py src/vibe3/services/pr_service.py tests/vibe3/commands/test_pr_create.py tests/vibe3/commands/test_pr_help.py
git commit -m "refactor(pr): replace draft command with create --draft"
```

### Task 3: Remove `pr merge` from public CLI

**Files:**
- Modify: `src/vibe3/commands/pr_lifecycle.py`
- Test: `tests/vibe3/commands/test_pr_merge.py`
- Docs: `docs/v3/handoff/02-flow-task-foundation.md`

**Step 1: Write the failing tests**

断言：

- `vibe3 pr merge` 不再出现在 help 中
- 调用 `vibe3 pr merge` 返回 “no such command”

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/vibe3/commands/test_pr_merge.py tests/vibe3/commands/test_pr_help.py -v`

Expected: FAIL

**Step 3: Remove the command registration**

- 从生命周期注册中移除 `merge`
- 不删除底层 service，除非确认无引用
- 只删除公开命令面

**Step 4: Run focused tests**

Run: `uv run pytest tests/vibe3/commands/test_pr_merge.py tests/vibe3/commands/test_pr_help.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add src/vibe3/commands/pr_lifecycle.py tests/vibe3/commands/test_pr_merge.py tests/vibe3/commands/test_pr_help.py docs/v3/handoff/02-flow-task-foundation.md
git commit -m "refactor(pr): remove merge from public command surface"
```

### Task 4: Move review gate behind an internal entry

**Files:**
- Modify: `scripts/hooks/pre-push.sh`
- Modify: `src/vibe3/commands/review_gate.py`
- Modify: `tests/vibe3/integration/test_review_shell_contract.py`

**Step 1: Write the failing tests**

断言：

- 顶层 help 不再显示 `review-gate`
- `pre-push.sh` 仍能调用内部入口
- shell contract 测试改为验证“未暴露公开命令，但 hook 入口稳定”

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/vibe3/integration/test_review_shell_contract.py -v`

Expected: FAIL

**Step 3: Implement minimal internalization**

推荐方式：

- 保留 `review_gate()` 函数
- 新增内部模块入口，例如 `python -m vibe3.commands.review_gate`
- `pre-push.sh` 调内部入口，不调公开 CLI 命令

不要再引入新的顶层命令或 `hooks` 子命令。

**Step 4: Run focused tests**

Run: `uv run pytest tests/vibe3/integration/test_review_shell_contract.py tests/vibe3/commands/test_review_gate.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add scripts/hooks/pre-push.sh src/vibe3/commands/review_gate.py tests/vibe3/integration/test_review_shell_contract.py tests/vibe3/commands/test_review_gate.py
git commit -m "refactor(review): hide review gate from public cli"
```

### Task 5: Tighten `pr show` as the only PR query surface

**Files:**
- Modify: `src/vibe3/commands/pr_query.py`
- Test: `tests/vibe3/commands/test_pr_show.py`

**Step 1: Write the failing tests**

覆盖：

- `pr show` 显示基本 PR 状态
- `pr show` 显示 CI / review comments / risk summary
- 不保留与版本 bump 无关的扩张查询面

**Step 2: Run tests to verify the gap**

Run: `uv run pytest tests/vibe3/commands/test_pr_show.py -v`

Expected: FAIL 或部分 FAIL

**Step 3: Implement minimal query narrowing**

- 保留 `show`
- 审查 `version_bump` 是否属于本轮范围外；若无明确包装价值，标记下一轮再处理或一并移出
- `show` 的人类输出重点聚焦交付承载视图

**Step 4: Run focused tests**

Run: `uv run pytest tests/vibe3/commands/test_pr_show.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add src/vibe3/commands/pr_query.py tests/vibe3/commands/test_pr_show.py
git commit -m "refactor(pr): focus show on delivery status"
```

### Task 6: Update design docs and handoff

**Files:**
- Modify: `docs/v3/handoff/02-flow-task-foundation.md`
- Modify: `.agent/context/task.md`
- Docs: `docs/plans/2026-03-20-pr-command-surface-design.md`
- Docs: `docs/plans/2026-03-20-pr-command-surface-plan.md`

**Step 1: Document the final command contract**

补齐以下事实：

- `task` 管目标
- `flow` 管现场
- `pr` 管交付承载
- `review` 管审查
- `integrate/done` 管 merge/closeout

**Step 2: Add local handoff context**

在 `.agent/context/task.md` 中记录：

- 当前分支
- 本轮目标
- 已批准的命令面结论
- 下一位 agent 的执行入口

**Step 3: Run doc-adjacent checks**

Run: `uv run pytest tests/vibe3/commands/test_pr_help.py tests/vibe3/integration/test_review_shell_contract.py -v`

Expected: PASS

**Step 4: Commit**

```bash
git add docs/v3/handoff/02-flow-task-foundation.md .agent/context/task.md docs/plans/2026-03-20-pr-command-surface-design.md docs/plans/2026-03-20-pr-command-surface-plan.md
git commit -m "docs(pr): record command-surface contract and handoff"
```

### Task 7: Final verification

**Files:**
- No new files

**Step 1: Run focused PR command suite**

Run:

```bash
uv run pytest \
  tests/vibe3/commands/test_pr_help.py \
  tests/vibe3/commands/test_pr_create.py \
  tests/vibe3/commands/test_pr_show.py \
  tests/vibe3/commands/test_pr_ready.py \
  tests/vibe3/commands/test_review_gate.py \
  tests/vibe3/integration/test_review_shell_contract.py -v
```

Expected: PASS

**Step 2: Run type checks**

Run: `uv run mypy src/vibe3`

Expected: `Success: no issues found`

**Step 3: Smoke test the final user-facing commands**

Run:

```bash
uv run python src/vibe3/cli.py pr --help
uv run python src/vibe3/cli.py pr show --help
uv run python src/vibe3/cli.py pr create --help
uv run python src/vibe3/cli.py pr ready --help
```

Expected:

- `pr` help 只保留 `create` / `show` / `ready`
- 顶层 help 不再出现 `review-gate`

**Step 4: Commit**

```bash
git add -A
git commit -m "test(pr): verify simplified command surface"
```
