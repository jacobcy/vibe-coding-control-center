# Executor Publish Directive: Issue #2206

## Context
Review completed with VERDICT = PASS. Ready for commit and PR creation.

## Commit Status
✅ Commit already exists: `7ddf4661 refactor(flow_lifecycle): eliminate redundant ConventionResolver calls`
✅ Commit message follows standards
✅ All tests passed
✅ No lint/type errors

## PR Creation Instructions

### PR Title
```
refactor(flow_lifecycle): eliminate redundant ConventionResolver calls
```

### PR Body
```markdown
## Summary
- Eliminate Roundabout Logic in `flow_lifecycle.py` by introducing `resolve_branch_and_issue()` helper
- Centralize branch resolution and issue number extraction into single function
- Remove duplicate `ConventionResolver` instantiations in `blocked()` and `rebuild()` functions

## Changes
- Added `resolve_branch_and_issue()` in `src/vibe3/services/branch_arg.py`
- Exported new function from `src/vibe3/services/__init__.py`
- Updated `blocked()` to use `resolve_branch_and_issue` (removed redundant resolver calls)
- Updated `rebuild()` to use `resolve_branch_and_issue` (removed redundant resolver calls)
- Removed `ConventionResolver` import from `flow_lifecycle.py` (no longer needed)

## Test Plan
- ✅ All 20 targeted tests passed:
  - `test_branch_arg.py`: 3/3 passed
  - `test_flow_lifecycle.py`: 5/5 passed
  - `test_issue_branch_resolver.py`: 12/12 passed
- ✅ ruff check: All checks passed
- ✅ mypy: Success - no issues found
- ✅ No behavior change (pure refactor)

## Review Notes
- Minor finding: New function lacks dedicated test (non-blocking - consumers are tested)
- All scope boundaries respected
- Backward compatibility preserved

Closes #2206

🤖 Generated with [Claude Code](https://claude.com/claude-code)
```

## Execution Steps
1. Verify commit exists and is clean
2. Push branch to remote (if not already pushed)
3. Create PR using `gh pr create`
4. Record PR reference in handoff

## Post-PR Actions
- Monitor CI checks
- Wait for human review and merge

## Notes
- This is a pure refactor with no behavior change
- Risk level: LOW
- All verification steps completed successfully
