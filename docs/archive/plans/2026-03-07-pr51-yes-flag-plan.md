# PR 51 Finishing Plan
I'm using the writing-plans skill to create the implementation plan.

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Wrap up PR #51 by exercising the new non-interactive `vibe task remove --yes` flow, keeping help output accurate, and proving the updated install/task tests plus review response clear the CI.

**Architecture:** The new `--yes` guard lives in `lib/task_actions.sh`; the tests stub branch management via `git` mock functions inside the `tests/test_task_ops.bats` fixture. We will keep that structure, explicitly pass `--yes` where branch cleanup occurs, and assert the helper admonishes users without the flag. After the tests pass locally we will reply to the PR review comment and push the refreshed branch so CI reruns.

**Tech Stack:** zsh scripts under `bin/` + `lib/`, Bats test runner (`tests/*.bats`), GitHub CLI for PR reviews.

---

### Task 1: Align the task removal tests with the new guard

**Files:**
- Modify: `tests/test_task_ops.bats:170-285`
- Confirm: `tests/test_task_core.bats:70-90`

**Step 1:** Update the branch-cleanup test so it calls `vibe_task remove --yes <task-id>`, records the mocked `branch -d`/`push --delete` calls, and still deletes the registry entry.

**Step 2:** Update the failure test to run `vibe_task remove --yes <task-id>` so branch residue is detected and the helper exits with the "Task removal blocked" warning and leaves the task in the registry.

**Step 3:** Verify the non-branch tests still pass without `--yes` and keep the `--help` assertion from `tests/test_task_core.bats` showing `[--yes]` in the usage.

**Step 4:** `git diff` should show the test cases now explicitly pass the new flag and the output assertions mention the new warning text.

### Task 2: Verify the focused Bats suite

**Files:**
- Verify: `tests/test_task_core.bats`
- Verify: `tests/test_task_ops.bats`

**Step 1:** Run `bats tests/test_task_core.bats tests/test_task_ops.bats`.
- Expected: `1..N` followed by `ok ...` lines and final `# 2 tests, 0 failures` (or the full Bats summary with zero failures).

**Step 2:** Record the command output to reference when updating the review comment.

### Task 3: Close the loop on PR #51

**Files:**
- Non-code: GitHub PR 51 review thread; `gh` commands.

**Step 1:** Add a review comment via `gh pr review 51 --repo jacobcy/vibe-coding-control-center --comment -b "..."` summarizing the new tests, mention the `scripts/install.sh` change still logs a warning, and note the local bats run.

**Step 2:** Push the branch: `git push origin codex/roadmap-skill` so PR 51 contains the new commits.

**Step 3:** Re-run `gh pr checks 51 --repo jacobcy/vibe-coding-control-center` to confirm the `Lint & Test` job is green. If it is still failing, gather the logs, adjust tests/code, and repeat the verification from Task 2.

---

**Change summary:** Approximately +40/-10 lines inside `tests/test_task_ops.bats` plus the new plan file and `tests/test_task_core.bats` updates to keep the help text accurate.
