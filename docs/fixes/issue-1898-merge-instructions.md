# Merge-Ready Handoff Instructions

## Current Status
- **Issue**: #1898 - 配置/素材缺失时给出友好错误与可执行诊断
- **Branch**: task/issue-1898
- **Review Verdict**: PASS
- **Commits**:
  - 7bef878e: fix(tests): update monkeypatch to use check_runtime_asset
  - a54d195f: fix(exceptions): move MissingResourceError to __init__.py to resolve circular import
  - 1e656d33: feat(exceptions): add MissingResourceError with diagnostic context

## Implementation Summary
Successfully implemented MissingResourceError with DiagnosticContext for user-friendly error messages:
- New exception class with diagnostic context
- 5 failure point wrappers (prompt-recipes, supervisor, assignee_dispatch, role-config, runtime-assets)
- E_CONFIG_MISSING error code registration
- Comprehensive test coverage (21 diagnostic tests)
- All tests pass (347 total, mypy clean, ruff clean)

## PR Creation Instructions

### Title Format
```
feat(exceptions): add MissingResourceError with diagnostic context
```

### PR Body Template
```markdown
## Summary
Implements user-friendly error messages for missing configuration and runtime assets.

## Changes
- Add MissingResourceError exception class with DiagnosticContext
- Wrap 5 key failure points with informative error messages:
  - prompt-recipes.yaml
  - supervisor.md
  - assignee_dispatch.yaml
  - role-config
  - runtime-assets
- Register E_CONFIG_MISSING error code
- Add comprehensive test coverage (21 tests)

## Test Results
✅ 347 tests passed (all target tests green)
✅ mypy clean
✅ ruff clean
✅ 6/6 tests in test_manager.py pass (retry fix verified)

## Follow-up
- Issue #2050: Refactor hardcoded E_CONFIG_MISSING string

Closes #1898
```

## Quality Checks Completed
- ✅ All tests pass
- ✅ Type checking (mypy) clean
- ✅ Linting (ruff) clean
- ✅ Scope boundary respected
- ✅ Review verdict: PASS

## Post-Merge Notes
- Issue #2050 tracks minor cleanup opportunity (hardcoded string)
- Implementation follows established patterns from error_codes.py and exception hierarchy
- No breaking changes to public APIs
