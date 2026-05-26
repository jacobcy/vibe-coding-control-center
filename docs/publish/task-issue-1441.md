# Publish Directive: task/issue-1441

## Objective
Create PR for issue #1441: fix manual CLI async dispatch failures

## Context
- **Issue**: #1441
- **Branch**: task/issue-1441
- **Commit**: 86f103d4 (already committed)
- **Verdict**: PASS (comprehensive audit completed)
- **Review**: Implementation correct, matches plan exactly

## Publish Instructions

1. **Execute vibe-commit skill**: Create PR using existing commit
   - Commit message already in place
   - No new commits needed
   - PR title: "fix: add error tracking for manual CLI async dispatch failures"
   - PR body: Reference issue #1441 and summarize changes

2. **PR Description Points**:
   - Added `record_dispatch_failure_if_unexpected()` helper to error_helpers.py
   - Wired helper into planner, executor, and reviewer roles
   - Helper filters normal throttling (capacity_full, duplicate_dispatch)
   - Records unexpected dispatch failures with tick_id=0
   - All tests pass, type/lint clean

3. **Post-PR Creation**:
   - Executor will produce pr_ref
   - State will auto-transition to state/handoff
   - Manager will verify PR quality in next round

## Quality Checks (Already Passed)
- Tests: 25/25 pass ✅
- Type checking: mypy clean ✅
- Linting: ruff clean ✅
- Git status: clean ✅

## Notes
- This is an additive-only change (no existing code paths altered)
- Impact: LOW risk (4 files, +64 LOC)
- No baseline concerns
