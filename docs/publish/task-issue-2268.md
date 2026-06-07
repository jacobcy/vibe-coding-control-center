# PR Publish Directive

## Issue
- Number: #2268
- Title: feat(orchestra): auto-resume 缺少熔断机制，同一 issue 可能在每次心跳时重复触发

## Branch
- Current: task/issue-2268
- Base: main

## Commit
- SHA: 5fc33a47
- Message: feat(orchestra): add cooldown mechanism to auto-resume circuit breaker

## PR Requirements

### Title
feat(orchestra): add cooldown mechanism to auto-resume circuit breaker

### Body Template
```markdown
## Summary
- Add module-level cooldown dictionary to `_auto_resume_to_ready()` in queue_operations.py
- Prevents the same issue from being retried within 300 seconds
- Prevents event log spam and API quota waste when LabelService.transition() fails repeatedly

## Changes
- Add `import time` and module-level cooldown tracking
- Add cooldown guard at the beginning of `_auto_resume_to_ready()`
- Clear cooldown on successful transition
- Add comprehensive unit tests (4 new tests)

## Test Plan
- ✅ 4/4 new tests pass (cooldown skip/allow/clear/independent)
- ✅ 145/145 orchestra tests pass (no regressions)
- ✅ mypy passes
- ✅ ruff passes

Closes #2268
```

## Notes
- Review verdict: PASS
- Minor note about cooldown recording order is non-blocking
- No scope violation detected
- Baseline diff: +14 LOC (minimal change)
