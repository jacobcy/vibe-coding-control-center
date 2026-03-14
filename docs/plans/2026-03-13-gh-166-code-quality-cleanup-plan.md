# GH-166 Code Quality Cleanup: Split Bats Suites and Clear Dead Code

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Split oversized Bats test suites into smaller topic-focused files and remove dead code functions to improve maintainability and review speed.

**Architecture:** Follow test-driven refactoring principles - split test files by topic while preserving coverage, then identify and remove dead code. Keep all changes within existing behavior boundaries.

**Tech Stack:** Bats (Bash Automated Testing System), ShellCheck, custom metrics dashboard

---

## Task 1: Analyze Current Test Structure

**Files:**
- Read: `tests/flow/test_flow_pr_review.bats`
- Read: `tests/flow/test_flow_lifecycle.bats`
- Read: `tests/task/test_task_ops.bats`
- Read: `tests/flow/test_flow_help_runtime.bats`
- Read: `tests/contracts/test_shared_state_contracts.bats`

**Step 1: Map test topics in largest Bats file**

Run:
```bash
grep "^@test" tests/flow/test_flow_pr_review.bats | wc -l
grep "^@test" tests/flow/test_flow_pr_review.bats
```

Expected: 891 lines, identify 3-5 logical topic groups (e.g., help, bump logic, base resolution, PR creation, web vs CLI)

**Step 2: Document proposed split strategy**

Create temporary notes:
```
tests/flow/test_flow_pr_review.bats (891 lines) →
  - tests/flow/pr/test_flow_pr_help.bats (~50 lines)
  - tests/flow/pr/test_flow_pr_bump.bats (~200 lines)
  - tests/flow/pr/test_flow_pr_base.bats (~300 lines)
  - tests/flow/pr/test_flow_pr_creation.bats (~250 lines)
  - tests/flow/pr/test_flow_pr_web.bats (~100 lines)
```

**Step 3: Commit analysis**

```bash
git add docs/plans/2026-03-13-gh-166-code-quality-cleanup-plan.md
git commit -m "docs(plan): add gh-166 code-quality cleanup strategy"
```

---

## Task 2: Split test_flow_pr_review.bats - Part 1 (Help Tests)

**Files:**
- Create: `tests/flow/pr/test_flow_pr_help.bats`
- Modify: `tests/flow/test_flow_pr_review.bats` (remove help tests)

**Step 1: Create new help test file**

Create `tests/flow/pr/test_flow_pr_help.bats`:
```bash
#!/usr/bin/env bats

source "$BATS_TEST_DIRNAME/../../helpers/flow_common.bash"

@test "1.1 vibe flow review help points to the supported Codex package" {
  run vibe flow review --help

  [ "$status" -eq 0 ]
  [[ "$output" =~ "@openai/codex" ]]
  [[ ! "$output" =~ "@anthropic/codex" ]]
  [[ "$output" =~ "[<pr-or-branch>|--branch <ref>]" ]]
}
```

**Step 2: Run new help test file**

Run: `bats tests/flow/pr/test_flow_pr_help.bats`
Expected: PASS (1 test)

**Step 3: Remove help test from original file**

Edit `tests/flow/test_flow_pr_review.bats`:
- Remove lines 5-12 (the help test)
- Update source path to use relative path from parent directory

**Step 4: Verify original file still passes**

Run: `bats tests/flow/test_flow_pr_review.bats`
Expected: PASS (all remaining tests)

**Step 5: Commit help test split**

```bash
git add tests/flow/pr/test_flow_pr_help.bats tests/flow/test_flow_pr_review.bats
git commit -m "test(flow): split PR help tests into dedicated file"
```

---

## Task 3: Split test_flow_pr_review.bats - Part 2 (Bump Logic Tests)

**Files:**
- Create: `tests/flow/pr/test_flow_pr_bump.bats`
- Modify: `tests/flow/test_flow_pr_review.bats` (remove bump tests)

**Step 1: Identify bump-related tests**

Run:
```bash
grep -n "bump" tests/flow/test_flow_pr_review.bats | grep "@test" | head -5
```

Expected: Find tests 12, 13, 14, 14.0 related to bump logic

**Step 2: Create bump test file**

Create `tests/flow/pr/test_flow_pr_bump.bats` with all bump-related tests:
```bash
#!/usr/bin/env bats

source "$BATS_TEST_DIRNAME/../../helpers/flow_common.bash"

@test "12. _flow_pr skips bump if PR already exists" {
  # Copy test implementation from original file
  run zsh -c '
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/flow.sh"
    _flow_resolve_pr_base() { echo "main"; return 0; }
    vibe_has() { return 0; }
    gh() {
      case "$*" in
        "pr list --state open --base main --json number,headRefName,title") echo "[]"; return 0 ;;
        "pr view current-branch") return 0 ;;
        "pr edit current-branch --base main --title test --body test") return 0 ;;
        *) return 0 ;;
      esac
    }
    git() {
      case "$*" in
        "branch --show-current") echo "current-branch"; return 0 ;;
        "fetch origin main --quiet") return 0 ;;
        "show-ref --verify --quiet refs/remotes/origin/main") return 0 ;;
        "log origin/main..HEAD --oneline") echo "abcdef test commit"; return 0 ;;
        "push origin HEAD") return 0 ;;
        *) return 0 ;;
      esac
    }
    _flow_pr --title "test" --body "test"
  '
  [ "$status" -eq 0 ]
  [[ "$output" =~ "Skipping version bump" ]]
}

# Add tests 13, 14, 14.0 similarly
```

**Step 3: Run bump test file**

Run: `bats tests/flow/pr/test_flow_pr_bump.bats`
Expected: PASS (all bump tests)

**Step 4: Remove bump tests from original**

Edit `tests/flow/test_flow_pr_review.bats`:
- Remove all bump-related test functions
- Verify no shared setup/teardown is broken

**Step 5: Verify split integrity**

Run:
```bash
bats tests/flow/pr/test_flow_pr_bump.bats
bats tests/flow/test_flow_pr_review.bats
```
Expected: Both PASS

**Step 6: Commit bump test split**

```bash
git add tests/flow/pr/test_flow_pr_bump.bats tests/flow/test_flow_pr_review.bats
git commit -m "test(flow): split PR bump logic tests into dedicated file"
```

---

## Task 4: Split test_flow_pr_review.bats - Part 3 (Base Resolution Tests)

**Files:**
- Create: `tests/flow/pr/test_flow_pr_base.bats`
- Modify: `tests/flow/test_flow_pr_review.bats` (remove base tests)

**Step 1: Identify base resolution tests**

Run:
```bash
grep -n "base" tests/flow/test_flow_pr_review.bats | grep "@test" | head -10
```

Expected: Tests 14.1, 14.2, 14.2.1, 14.3, 14.3.1, 14.3.2, 14.4, 14.4.1, 14.5, 14.6

**Step 2: Create base test file**

Create `tests/flow/pr/test_flow_pr_base.bats` with all base-related tests (follow same pattern as Task 3)

**Step 3: Run base test file**

Run: `bats tests/flow/pr/test_flow_pr_base.bats`
Expected: PASS

**Step 4: Remove base tests from original**

**Step 5: Verify split integrity**

Run:
```bash
bats tests/flow/pr/test_flow_pr_base.bats
bats tests/flow/test_flow_pr_review.bats
```

**Step 6: Commit base test split**

```bash
git add tests/flow/pr/test_flow_pr_base.bats tests/flow/test_flow_pr_review.bats
git commit -m "test(flow): split PR base resolution tests into dedicated file"
```

---

## Task 5: Split test_flow_lifecycle.bats

**Files:**
- Read: `tests/flow/test_flow_lifecycle.bats`
- Create: `tests/flow/lifecycle/test_flow_lifecycle_basic.bats`
- Create: `tests/flow/lifecycle/test_flow_lifecycle_state.bats`
- Create: `tests/flow/lifecycle/test_flow_lifecycle_task_binding.bats`

**Step 1: Analyze lifecycle test topics**

Run:
```bash
grep "^@test" tests/flow/test_flow_lifecycle.bats
wc -l tests/flow/test_flow_lifecycle.bats
```

Expected: 590 lines, identify 2-3 topic groups

**Step 2: Create split files**

Follow same pattern as Tasks 2-4 to split into:
- Basic lifecycle operations
- State management
- Task binding

**Step 3: Run all new test files**

Run: `bats tests/flow/lifecycle/*.bats`
Expected: All PASS

**Step 4: Remove split tests from original**

**Step 5: Verify no regressions**

Run: `bats tests/flow/test_flow_lifecycle.bats tests/flow/lifecycle/*.bats`

**Step 6: Commit lifecycle test split**

```bash
git add tests/flow/lifecycle/*.bats tests/flow/test_flow_lifecycle.bats
git commit -m "test(flow): split lifecycle tests into topic-focused files"
```

---

## Task 6: Split test_task_ops.bats

**Files:**
- Read: `tests/task/test_task_ops.bats`
- Create: `tests/task/ops/test_task_ops_crud.bats`
- Create: `tests/task/ops/test_task_ops_query.bats`
- Create: `tests/task/ops/test_task_ops_binding.bats`

**Step 1: Analyze task ops test topics**

Run:
```bash
grep "^@test" tests/task/test_task_ops.bats
wc -l tests/task/test_task_ops.bats
```

Expected: 573 lines

**Step 2-6: Follow same split pattern**

Create topic-focused files, verify, commit.

---

## Task 7: Verify Test Coverage Preservation

**Files:**
- Test: All split test files

**Step 1: Run full test suite before dead code cleanup**

Run:
```bash
bats tests/
bash scripts/lint.sh
```

Expected: All PASS, 0 errors

**Step 2: Count test count before and after splits**

Run:
```bash
grep -r "^@test" tests/ | wc -l
```

Expected: Same count as before splits (coverage preserved)

**Step 3: Check file size distribution**

Run:
```bash
find tests/ -name "*.bats" -exec wc -l {} \; | sort -rn | head -10
```

Expected: No file exceeds 400 lines

**Step 4: Commit verification**

```bash
git add docs/plans/2026-03-13-gh-166-code-quality-cleanup-plan.md
git commit -m "test: verify test coverage preserved after splits"
```

---

## Task 8: Identify Dead Code Functions

**Files:**
- Run: `scripts/metrics.sh`
- Read: `lib/*.sh` (dead code candidates)

**Step 1: Run metrics dashboard**

Run: `bash scripts/metrics.sh 2>&1 | grep -A 5 "死代码函数"`

Expected: List of 6 dead code functions with locations

**Step 2: Manually verify each dead function**

For each reported function:
```bash
grep -r "function_name" lib/ bin/ --include="*.sh"
grep -r "function_name" tests/ --include="*.bats"
```

Expected: Confirm zero call sites

**Step 3: Document dead code findings**

Create list:
```
Dead functions to remove:
1. lib/xyz.sh:_unused_helper_1
2. lib/abc.sh:_deprecated_wrapper
...
```

**Step 4: Commit analysis**

```bash
git add docs/plans/2026-03-13-gh-166-code-quality-cleanup-plan.md
git commit -m "docs(plan): document dead code removal targets"
```

---

## Task 9: Remove Dead Code Functions

**Files:**
- Modify: Various `lib/*.sh` files (exact files depend on Task 8 findings)

**Step 1: Remove first dead function**

For each dead function:
```bash
# Example: Remove _unused_helper from lib/xyz.sh
# Use Edit tool to remove the function definition
```

**Step 2: Verify removal doesn't break tests**

Run: `bats tests/`
Expected: PASS

**Step 3: Verify metrics updated**

Run: `bash scripts/metrics.sh | grep "死代码函数"`
Expected: Count decreased by 1

**Step 4: Commit each removal**

```bash
git add lib/xyz.sh
git commit -m "refactor: remove unused helper _unused_helper_1"
```

**Step 5: Repeat for all dead functions**

Repeat Steps 1-4 for each identified dead function.

---

## Task 10: Final Verification and Guardrails Check

**Files:**
- Verify: All modified files
- Run: All verification scripts

**Step 1: Run full test suite**

Run: `bats tests/`
Expected: All PASS

**Step 2: Run linting**

Run: `bash scripts/lint.sh`
Expected: 0 errors (warnings OK)

**Step 3: Check metrics dashboard**

Run: `bash scripts/metrics.sh`
Expected:
- 死代码函数 = 0
- bin/ + lib/ LOC < 7000
- No file exceeds 300 lines

**Step 4: Verify test file sizes**

Run:
```bash
find tests/ -name "*.bats" -exec wc -l {} \; | sort -rn | head -5
```

Expected: Largest test file < 400 lines

**Step 5: Final commit**

```bash
git add .
git commit -m "chore: final verification for gh-166 code-quality cleanup"
```

---

## Acceptance Criteria Verification

After completing all tasks, verify:

- [x] Top oversized Bats suites split into smaller topic-focused files
- [x] `bash scripts/lint.sh` passes
- [x] `bats tests/` passes
- [x] `bash scripts/metrics.sh` reports 死代码函数 = 0
- [x] No shell file exceeds 300 lines
- [x] `bin/ + lib/` remains within 7000 LOC ceiling

---

## Related Issues

- Parent cleanup theme: #121
- Metrics dashboard context
- Test maintainability improvement
