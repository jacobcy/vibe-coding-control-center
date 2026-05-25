# Executor Publish Instructions - Issue #1385

## Context

- **Issue**: #1385 - test(error-tracking): add _display_error_tracking() tests and missing get_all_errors_status() edge cases
- **Branch**: task/issue-1385
- **Commit**: 050538b1 (already created)
- **State**: state/merge-ready
- **Verdict**: PASS (credible review)

## Task

Create PR for the completed test additions.

## PR Requirements

**Title**: 
```
test(error-tracking): add missing tests from PR #1380
```

**Body**:
```markdown
## Summary
Re-add tests lost during PR #1380 rebase conflicts:
- Add `TestDisplayErrorTracking` class with 4 tests covering `_display_error_tracking()` display behavior
- Add 5 `get_all_errors_status()` edge case tests

## Test Coverage
- **TestDisplayErrorTracking** (4 tests):
  - `test_display_historical_errors_windowed_zero`
  - `test_display_historical_and_windowed_both_nonzero`
  - `test_display_no_errors`
  - `test_display_with_recent_errors_table`
  
- **get_all_errors_status edge cases** (5 tests):
  - `test_get_all_errors_status_empty_db`
  - `test_get_all_errors_status_single_severity`
  - `test_get_all_errors_status_severity_buckets`
  - `test_get_all_errors_status_null_severity_via_service_defaults_to_error`
  - `test_get_all_errors_status_ignores_time_window`

## Verification
- All 42 tests pass (17 + 17 + 8 other tests)
- No source code changes (pure test additions)
- Commit: 050538b1

## References
- Fixes #1385
- Ref: #1380 (commit b9d37e3c)
- Ref: #1334 (original test coverage requirement)

🤖 Generated with [Claude Code](https://claude.com/claude-code)
```

## Checklist Before Creating PR

1. ✅ All tests pass
2. ✅ No source code changes
3. ✅ Commit message follows conventional commits
4. ✅ Co-authored-by line included

## Notes

- Pure test additions, LOW risk
- Review verdict: PASS (verified each test assertion against implementation)
- No breaking changes

## After PR Creation

- PR reference will be recorded as `pr_ref`
- Manager will verify PR content matches plan/spec
- Transition to `state/done` after PR approval
