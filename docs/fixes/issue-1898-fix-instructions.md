# Fix Instructions for Issue #1898

## Context

Review completed with MAJOR verdict. 3 test regressions found that executor report omitted.

## Critical Issues to Fix

### 1. [MAJOR] Fix test regressions in test_manager.py

**Location**: `tests/vibe3/roles/test_manager.py:74,133,187`

**Problem**: Tests monkeypatch `vibe3.roles.manager.resolve_prompts_path` which no longer exists after executor replaced it with `check_runtime_asset`.

**Fix**: Update the 3 monkeypatch calls from:
```python
monkeypatch.setattr("vibe3.roles.manager.resolve_prompts_path", lambda: prompts_path)
```

to:
```python
monkeypatch.setattr("vibe3.roles.manager.check_runtime_asset", lambda path: prompts_path)
```

**Verification**: Run `uv run pytest tests/vibe3/roles/test_manager.py -v` and confirm all tests pass.

## Minor Issues (Optional Fixes)

### 2. [MINOR] Hardcoded error code in cli.py:291

**Location**: `src/vibe3/cli.py:291`

**Problem**: Uses hard-coded string `"E_CONFIG_MISSING"` instead of importing the constant.

**Fix**: Import and use the constant from `error_codes.py`.

## Scope Boundary

- Fix only the test regressions (MAJOR issue)
- Minor issues can be fixed if straightforward, but not required
- Do NOT make additional changes beyond these fixes

## Reference

Full audit report: `docs/reports/issue-1898-audit-report.md`
View with: `vibe3 handoff show docs/reports/issue-1898-audit-report.md --branch task/issue-1898`