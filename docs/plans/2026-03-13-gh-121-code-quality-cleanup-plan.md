# GH-121 Code Quality Cleanup Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在不干扰 `gh-152 / PR #161` 收口的前提下，完成 `#121 audit(code-quality)` 的第一轮可执行清理，优先删除真死代码、补齐分类证据，并收敛非 `gh-152` 范围内的低质量代码与重复测试。

**Architecture:** 本轮只做审计后可独立落地的小改动，不做跨 PR 责任重分配。策略分三段：先删除已确认的内部死代码 helper，再把“复杂但不该删”的目标单独归类为 follow-up，最后对重复/低信号测试做最小收敛。`lib/task_query.sh`、其测试面、以及 `#161` 讨论中的截图/评论语义全部排除，保留给 `gh-152` 自己处理。

**Tech Stack:** Zsh shell, jq, bats, gh CLI

---

## Scope And Exclusions

**In scope**
- `lib/check_pr_status.sh`
- `lib/flow.sh`
- `lib/roadmap_store.sh`
- 受这些 helper 影响的直接测试
- 非 `gh-152` 范围内的重复/脆弱测试审计与最小收敛

**Explicitly out of scope**
- `lib/task_query.sh`
- `lib/task.sh` 中为了配合 `task_query.sh` 拆分而发生的结构调整
- `gh-152 / PR #161` 已发布代码面的 LOC 修复
- PR `#161` 截图、review thread、review evidence 的内容改写
- 大规模 shell 架构重写

**Execution guardrail**
- 若某项清理需要改动 `task_query` 路径、`flow/task` runtime contract，立即停止并转记为 `gh-152` follow-up，不在 `#121` 内实现。

### Task 1: Freeze The Cleanup Boundary

**Files:**
- Modify: `.agent/context/task.md`
- Reference: `docs/plans/2026-03-13-gh-121-code-quality-cleanup-plan.md`
- Reference: `lib/task_query.sh`

**Step 1: Record the exclusion boundary**

在 handoff 或执行记录中明确写入：

```md
- GH-121 excludes lib/task_query.sh and any PR #161-only cleanup.
```

**Step 2: Verify the current PR boundary before changing code**

Run:

```bash
vibe flow show --json
gh pr view 161 --json number,title,state,mergeStateStatus
```

Expected:
- 当前 worktree 仍绑定 `gh-152`
- `#161` 仍是 open/blocked 或 open/pending 状态

**Step 3: Commit the planning artifact**

```bash
git add .agent/context/task.md docs/plans/2026-03-13-gh-121-code-quality-cleanup-plan.md
git commit -m "docs(plan): scope gh-121 code-quality cleanup"
```

### Task 2: Delete Confirmed Dead Helpers In `roadmap_store`

**Files:**
- Modify: `lib/roadmap_store.sh`
- Test: `tests/roadmap/test_roadmap_write_audit.bats`
- Test: `tests/roadmap/test_roadmap_status_render.bats`
- Test: `tests/contracts/test_roadmap_contract.bats`

**Step 1: Write or extend failing safety tests around current behavior**

Add coverage only for externally observable behavior, not for private helpers:

```bash
bats tests/roadmap/test_roadmap_write_audit.bats \
     tests/roadmap/test_roadmap_status_render.bats \
     tests/contracts/test_roadmap_contract.bats
```

Expected:
- 当前测试全部通过，作为删除前基线

**Step 2: Remove the unused helpers**

Delete only these private helpers if call-site search still returns zero:

```zsh
_vibe_roadmap_has_version_goal
_vibe_roadmap_get_current_issues
```

**Step 3: Re-run the focused tests**

Run:

```bash
bats tests/roadmap/test_roadmap_write_audit.bats \
     tests/roadmap/test_roadmap_status_render.bats \
     tests/contracts/test_roadmap_contract.bats
```

Expected:
- PASS

**Step 4: Commit**

```bash
git add lib/roadmap_store.sh tests/roadmap/test_roadmap_write_audit.bats tests/roadmap/test_roadmap_status_render.bats tests/contracts/test_roadmap_contract.bats
git commit -m "refactor(roadmap): remove unused store helpers"
```

### Task 3: Delete Confirmed Dead Helper In `flow`

**Files:**
- Modify: `lib/flow.sh`
- Test: `tests/flow/test_flow_help_runtime.bats`
- Test: `tests/flow/test_flow_pr_review.bats`
- Test: `tests/contracts/test_flow_contract.bats`

**Step 1: Verify `_flow_shared_dir` still has zero call sites**

Run:

```bash
rg -n "_flow_shared_dir" lib tests bin scripts
```

Expected:
- Only the definition remains

**Step 2: Remove the helper**

Delete:

```zsh
_flow_shared_dir
```

Do not refactor unrelated flow helpers in the same pass.

**Step 3: Re-run focused flow tests**

Run:

```bash
bats tests/flow/test_flow_help_runtime.bats \
     tests/flow/test_flow_pr_review.bats \
     tests/contracts/test_flow_contract.bats
```

Expected:
- PASS

**Step 4: Commit**

```bash
git add lib/flow.sh tests/flow/test_flow_help_runtime.bats tests/flow/test_flow_pr_review.bats tests/contracts/test_flow_contract.bats
git commit -m "refactor(flow): remove unused shared-dir helper"
```

### Task 4: Classify `check_pr_status` Helper Instead Of Blind Deletion

**Files:**
- Modify: `lib/check_pr_status.sh`
- Modify: `lib/roadmap_dependency.sh`
- Test: `tests/roadmap/test_roadmap_query.bats`
- Reference: `docs/plans/2026-03-13-gh-121-code-quality-cleanup-plan.md`

**Step 1: Verify whether `_check_pr_merged_status` is truly dead or just obsolete**

Run:

```bash
rg -n "_check_pr_merged_status|uncertain_tasks" lib tests bin scripts
```

Expected:
- Either zero callers, or only historical/internal references

**Step 2: Choose exactly one outcome**

Allowed outcomes:
- Remove it if it has no externally required behavior
- Keep it and add an explicit comment if it is a reserved compatibility hook
- Move it to a future follow-up if removing it would entangle `gh-152` or broader runtime semantics

Do not invent a new feature to “justify” keeping it.

**Step 3: Re-run dependency query tests**

Run:

```bash
bats tests/roadmap/test_roadmap_query.bats
```

Expected:
- PASS

**Step 4: Commit**

If removed:

```bash
git add lib/check_pr_status.sh lib/roadmap_dependency.sh tests/roadmap/test_roadmap_query.bats
git commit -m "refactor(check): remove unused merged-status helper"
```

If kept as follow-up only:

```bash
git add docs/plans/2026-03-13-gh-121-code-quality-cleanup-plan.md
git commit -m "docs(plan): classify check-pr-status cleanup boundary"
```

### Task 5: Audit Repeated And Low-Signal Tests Outside `gh-152`

**Files:**
- Modify: `tests/roadmap/test_roadmap_write_audit.bats`
- Modify: `tests/roadmap/test_roadmap_status_render.bats`
- Modify: `tests/contracts/test_roadmap_contract.bats`
- Modify: `tests/flow/test_flow_help_runtime.bats`
- Modify: `tests/flow/test_flow_pr_review.bats`
- Modify: `tests/contracts/test_flow_contract.bats`

**Step 1: Identify duplicated assertions**

Look for:
- Same setup + same assertion repeated in contract and behavior tests
- Assertions that only restate fixture contents rather than module behavior
- Tests that lock private helper layout instead of public command output

**Step 2: Remove only redundant assertions or duplicate cases**

Allowed:
- Merge duplicate expectations into one stronger test
- Drop fixture-restatement assertions with no behavioral signal

Not allowed:
- Shrinking coverage to hide regressions
- Touching tests that exist only because of `task_query.sh` or `gh-152`

**Step 3: Re-run the exact touched suites**

Run:

```bash
bats tests/roadmap/test_roadmap_write_audit.bats \
     tests/roadmap/test_roadmap_status_render.bats \
     tests/contracts/test_roadmap_contract.bats \
     tests/flow/test_flow_help_runtime.bats \
     tests/flow/test_flow_pr_review.bats \
     tests/contracts/test_flow_contract.bats
```

Expected:
- PASS

**Step 4: Commit**

```bash
git add tests/roadmap/test_roadmap_write_audit.bats tests/roadmap/test_roadmap_status_render.bats tests/contracts/test_roadmap_contract.bats tests/flow/test_flow_help_runtime.bats tests/flow/test_flow_pr_review.bats tests/contracts/test_flow_contract.bats
git commit -m "test: remove redundant non-gh-152 coverage"
```

### Task 6: Final Verification And Issue-121 Output

**Files:**
- Modify: `.agent/context/task.md`
- Reference: `docs/plans/2026-03-13-gh-121-code-quality-cleanup-plan.md`

**Step 1: Run final targeted verification**

Run:

```bash
bash scripts/lint.sh
bats tests/roadmap/test_roadmap_query.bats \
     tests/roadmap/test_roadmap_write_audit.bats \
     tests/roadmap/test_roadmap_status_render.bats \
     tests/contracts/test_roadmap_contract.bats \
     tests/flow/test_flow_help_runtime.bats \
     tests/flow/test_flow_pr_review.bats \
     tests/contracts/test_flow_contract.bats
```

Expected:
- lint passes with 0 new errors
- focused test suites pass

**Step 2: Summarize outcomes for `#121`**

Post a summary containing:
- removed helpers
- kept helpers and why
- follow-ups explicitly deferred to `gh-152 / PR #161`
- any remaining duplicate-test candidates not handled in this pass

**Step 3: Update handoff**

Record:

```md
- target: gh-121
- plan: docs/plans/2026-03-13-gh-121-code-quality-cleanup-plan.md
- next: /vibe-start
```

