# Publish Directive: Issue #2202

## Context
- Issue: #2202 - 系统改进：将 PR symbols 添加到 models 公共 API
- Branch: task/issue-2202
- Commit: 69087369 (already committed)
- Verdict: PASS
- State: merge-ready

## Task
Execute commit + PR creation for issue #2202.

## Commit Instructions
✅ **Commit already exists** (1cdb81c3):
- Commit message follows standards
- Changes already committed
- No additional commit needed

## PR Creation Instructions
Create a PR with the following specifications:

### PR Title
```
feat(models): add CICheck and UpdatePRRequest to public API
```

### PR Body
```markdown
## Summary
- Added `CICheck` and `UpdatePRRequest` to models public API
- Symbols can now be imported via `from vibe3.models import CICheck, UpdatePRRequest`
- Added verification tests for importability and `__all__` membership

## Changes
- `src/vibe3/models/__init__.py`:
  - Added CICheck and UpdatePRRequest to TYPE_CHECKING import block
  - Added both symbols to _LAZY_IMPORTS for lazy loading
  - Added both symbols to __all__ for public API exposure
- `tests/vibe3/test_public_api_exports.py`:
  - Added test_models_pr_symbols_importable to verify imports work
  - Added test_models_all_contains_pr_symbols to verify __all__ membership

## Test Results
- ✅ 19 tests passed in test_public_api_exports.py
- ✅ 133 tests passed in tests/vibe3/models/ (no regressions)
- ✅ mypy: Success (no type errors)
- ✅ ruff: All checks passed (no lint errors)

## Related Issues
- Closes #2202
- See also #2232 (follow-up: remove duplicate PlanRequest from __all__)

🤖 Generated with [Claude Code](https://claude.com/claude-code)
```

### PR Options
- Base branch: main
- Draft: false (ready for review)
- Labels: (will be inherited from issue)

## Post-PR Creation
1. Record PR reference to `pr_ref` in flow state
2. Transition issue to `state/done` after PR is created
3. Write issue comment confirming PR creation

## Notes
- Both symbols were already defined in `vibe3.models.pr` and used extensively
- This change only exposes them through public API path
- No breaking changes or behavior modifications
