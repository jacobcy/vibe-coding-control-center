# PR Ready Human-Only Convergence Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 pr ready 收敛为 human-only 命令，只负责 gh ready 与 PR reviewer briefing；移除本地门禁和 state/merge-ready 自动流转，并同步最小必要文档。

**Architecture:** 本地质量门禁继续由 pre-push 和 CI 承担，pr ready 不再决定“能否进入 review”。pr ready 保留为一个人类操作入口，在执行 gh pr ready 前后生成可复用的 reviewer briefing 评论，为 @codex、@copilot、@auggie、@claude 提供统一上下文。

**Tech Stack:** Python, Typer, GitHub CLI, pytest, existing inspect/review/snapshot services

---

## Decision Audit

### What pre-push already covers

- Compile check: `uv run python -m compileall -q src/vibe3`
- Type check: `uv run mypy src`
- Incremental or fallback pytest targets via `vibe3.analysis.pre_push_test_selector`
- Inspect-based risk assessment via `vibe3 inspect base <REVIEW_BASE> --json`
- High-risk async review trigger via `vibe3 review base <REVIEW_BASE> --async` when score reaches block threshold

### What pre-push does not cover

- Coverage gate from `CoverageService`
- Blocking wait for review result before push
- `inspect pr`-specific risk check for an already-created PR
- `state/merge-ready` label sync

### Decision

- `pr ready` can safely stop doing local gates.
- Do not move coverage gate into pre-push in this change.
- Keep upstream conflict check inside `PRService.mark_ready()` because it is action validity, not policy gating.

## Chunk 1: Remove PR Ready Gates

### Task 1: Narrow command semantics

**Files:**
- Modify: `src/vibe3/commands/pr_lifecycle.py`
- Modify: `src/vibe3/services/pr_ready_usecase.py`
- Test: `tests/vibe3/commands/test_pr_ready.py`
- Test: `tests/vibe3/services/test_pr_ready_usecase.py`

- [ ] **Step 1: Write failing tests for gate removal**

Add tests asserting:
- `pr ready` no longer invokes coverage gate
- `pr ready` no longer invokes risk gate
- `--yes` only affects confirmation behavior, not quality gate bypass

- [ ] **Step 2: Run targeted tests to verify failure**

Run: `uv run pytest tests/vibe3/commands/test_pr_ready.py tests/vibe3/services/test_pr_ready_usecase.py -q`
Expected: failures referencing legacy gate calls or old `--yes` semantics

- [ ] **Step 3: Remove command-scoped gate orchestration**

Update `src/vibe3/commands/pr_lifecycle.py` to:
- delete `_run_ready_gates()`
- stop wiring `pr_quality_gates` into `_build_pr_ready_usecase()`
- update help text and docstring to reflect human-only behavior

Update `src/vibe3/services/pr_ready_usecase.py` to:
- remove `gate_runner` dependency
- keep only confirmation + mark ready flow

- [ ] **Step 4: Run targeted tests to verify pass**

Run: `uv run pytest tests/vibe3/commands/test_pr_ready.py tests/vibe3/services/test_pr_ready_usecase.py -q`
Expected: PASS

### Task 2: Decide compatibility of `--yes`

**Files:**
- Modify: `src/vibe3/commands/pr_lifecycle.py`
- Test: `tests/vibe3/commands/test_pr_ready.py`

- [ ] **Step 1: Keep `--yes` as confirmation bypass only**

Implement the narrowest behavior:
- if `--yes`, skip interactive confirm
- do not mention “绕过业务逻辑检查” in help text

- [ ] **Step 2: Validate help output contract**

Run: `uv run python src/vibe3/cli.py pr ready --help`
Expected: no coverage/risk gate wording remains

## Chunk 2: Add PR Reviewer Briefing Comment

### Task 3: Build briefing payload from existing analysis primitives

**Files:**
- Create: `src/vibe3/services/pr_review_briefing_service.py`
- Modify: `src/vibe3/services/pr_service.py`
- Modify: `src/vibe3/clients/protocols.py`
- Modify: `src/vibe3/clients/github_pr_ops.py`
- Test: `tests/vibe3/services/test_pr_review_briefing_service.py`
- Test: `tests/vibe3/services/test_pr_service.py`

- [ ] **Step 1: Write failing service tests**

Cover:
- renders compact reviewer briefing body
- includes PR metadata, linked issue, inspect summary, changed symbols, snapshot diff summary when available
- degrades gracefully when snapshot diff is unavailable

- [ ] **Step 2: Run tests to verify failure**

Run: `uv run pytest tests/vibe3/services/test_pr_review_briefing_service.py tests/vibe3/services/test_pr_service.py -q`
Expected: missing service or missing client method failures

- [ ] **Step 3: Implement briefing service**

The service should reuse existing sources where practical:
- `inspect pr` summary from `src/vibe3/commands/inspect_pr_helpers.py` or `inspect_output_adapter`
- changed symbols from existing inspect JSON adapters
- snapshot diff summary from `build_snapshot_diff()` when local branch matches PR head branch

The comment body should stay short and stable:
- PR number, title, base/head
- linked issue
- file and LOC delta summary
- changed symbols grouped by file
- dependency or structure hints when present
- explicit “Please focus on” section

- [ ] **Step 4: Add PR comment upsert support**

Add minimal GitHub client capability to:
- find existing bot-authored briefing comment by sentinel marker
- create comment if missing
- update comment if present

Prefer one stable marker such as `<!-- vibe3:pr-review-briefing -->`.

- [ ] **Step 5: Wire briefing publication into `PRService.mark_ready()`**

Order:
- resolve PR
- mark ready if still draft
- publish or update briefing comment on PR
- record flow event

- [ ] **Step 6: Run targeted tests**

Run: `uv run pytest tests/vibe3/services/test_pr_review_briefing_service.py tests/vibe3/services/test_pr_service.py tests/vibe3/commands/test_pr_ready.py -q`
Expected: PASS

## Chunk 3: Remove Merge-Ready Auto Sync

### Task 4: Stop mutating `state/merge-ready` from `pr ready`

**Files:**
- Modify: `src/vibe3/services/pr_ready_usecase.py`
- Modify: `tests/vibe3/services/test_pr_ready_usecase.py`
- Optional Modify: `docs/standards/github-labels-standard.md`

- [ ] **Step 1: Write failing test for label sync removal**

Assert `pr ready` does not call `LabelService.confirm_issue_state(..., IssueState.MERGE_READY, ...)`.

- [ ] **Step 2: Run targeted test to verify failure**

Run: `uv run pytest tests/vibe3/services/test_pr_ready_usecase.py -q`
Expected: failure still expecting merge-ready sync

- [ ] **Step 3: Remove `_sync_merge_ready_label()` path**

Delete merge-ready sync logic from `PrReadyUsecase`.

- [ ] **Step 4: Run targeted test to verify pass**

Run: `uv run pytest tests/vibe3/services/test_pr_ready_usecase.py -q`
Expected: PASS

## Chunk 4: Retire `vibe-task` Mirror Semantics and Update Docs

### Task 5: Update standards and direct command docs

**Files:**
- Modify: `docs/standards/quality-control-standard.md`
- Modify: `docs/standards/github-labels-standard.md`
- Modify: `skills/vibe-task/SKILL.md`
- Optional Modify: `docs/standards/github-labels-reference.md`

- [ ] **Step 1: Update quality-control standard**

Document that:
- pre-push owns local compile/type/test/risk checks
- `pr ready` is human-only and no longer a gate
- coverage remains CI or explicit manual verification, not part of `pr ready`

- [ ] **Step 2: Remove `vibe-task` mirror label claims from active standards**

Change active wording from “执行项镜像标签” to roadmap/flow-based semantics.

- [ ] **Step 3: Update `skills/vibe-task/SKILL.md`**

Avoid describing `vibe-task` as an active label or registration truth.

- [ ] **Step 4: Validate key doc strings**

Run: `rg -n "coverage gate|质量门禁|vibe-task|merge-ready" docs/standards skills/vibe-task src/vibe3/commands/pr_lifecycle.py src/vibe3/services/pr_ready_usecase.py`
Expected: only intentional references remain

## Chunk 5: Verification and Rollout Safety

### Task 6: Run focused regression verification

**Files:**
- Test: `tests/vibe3/commands/test_pr_ready.py`
- Test: `tests/vibe3/services/test_pr_ready_usecase.py`
- Test: `tests/vibe3/services/test_pr_service.py`
- Test: `tests/vibe3/services/test_pr_review_briefing_service.py`

- [ ] **Step 1: Run focused suite**

Run: `uv run pytest tests/vibe3/commands/test_pr_ready.py tests/vibe3/services/test_pr_ready_usecase.py tests/vibe3/services/test_pr_service.py tests/vibe3/services/test_pr_review_briefing_service.py -q`
Expected: PASS

- [ ] **Step 2: Run hook contract smoke check**

Run: `bash scripts/hooks/pre-push.sh </dev/null`
Expected: if fallback scope resolves locally, script completes or fails only for genuine environment reasons; no dependency on `pr ready`

- [ ] **Step 3: Manual CLI smoke checks**

Run:
- `uv run python src/vibe3/cli.py pr ready --help`
- `uv run python src/vibe3/cli.py review --help`

Expected:
- `pr ready` help shows human-only semantics
- `review` remains the dedicated analysis path

## Rollout Notes

- Do not add coverage execution into pre-push in this change. It would turn every push into a second full pytest run.
- Keep `check_upstream_conflicts()` inside `PRService.mark_ready()`.
- Prefer PR comment publication over issue comment publication. If no PR exists, briefing should not silently fall back to issue comment in this change.
- If comment upsert support is too large, phase the rollout: first create-only comment, then add update behavior in a follow-up.