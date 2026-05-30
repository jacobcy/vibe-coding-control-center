# Executor Publish Directive

## Task
Create PR for issue #1663 - Cross-Project Config Loading Fix

## Commit
- SHA: 2361eb86
- Message: fix(config): add vibe3 config root fallback for cross-project invocation
- Branch: task/issue-1663
- Base branch: main

## PR Requirements

### Title
fix(config): add vibe3 config root fallback for cross-project invocation

### Description Template
```markdown
## Summary
- Fixes #1663: Cross-project vibe3 invocation now correctly loads agent_config
- Root cause: Config loader used CWD-relative paths which failed from external projects
- Solution: Added `_vibe3_config_root()` helper to find vibe3 installation directory as fallback

## Changes
- **settings.py**: Added `_vibe3_config_root()` helper to locate vibe3 installation directory
- **settings.py**: Modified `get_defaults()` to check vibe3 config root after CWD checks fail
- **settings.py**: Modified `_load_supplementary()` to accept config_path parameter for relative resolution
- **loader.py**: Modified `find_config_file()` to include vibe3 config root in search path (step 4)
- **loader.py**: Modified `load_config()` to fallback to vibe3 config root for repo_config_path

## Testing
- ✅ 75/75 config tests pass
- ✅ Manual verification from /tmp successful
- ✅ Type checking (mypy) pass
- ✅ Linting (ruff) pass
- ✅ All existing tests pass (backward compatibility preserved)

## Notes
- Backward compatible: CWD-local config still has priority
- Created follow-up issue #1690 for pre-existing config naming inconsistency
```

## Review Reference
- Audit report: docs/reports/issue-1663-audit-report.md
- Verdict: PASS

## After PR Creation
- PR reference will be recorded as pr_ref
- Issue will transition to state/done after manager reviews PR

## Important
- Ensure PR targets main branch
- Verify CI passes before reporting completion
- If CI fails, report failure in handoff and remain in merge-ready state
