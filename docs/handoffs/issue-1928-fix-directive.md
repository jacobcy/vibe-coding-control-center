# Fix Directive for Issue #1928

## Verdict: MAJOR

## Issues to Fix

### Issue 1: Wrong `parents[]` index in `installed_vibe_home` fixture (MAJOR)

**Location**: `tests/vibe3/integration/test_cross_project_prompt_smoke.py:94`

**Problem**: Line 94 uses `parents[4]` instead of `parents[3]`, creating an empty temp directory with no assets copied. All tests exercise bundled fallback instead of cross-project global asset discovery.

**Fix**: Change line 94:
```python
# Before (wrong):
project_root = Path(__file__).resolve().parents[4]

# After (correct):
project_root = Path(__file__).resolve().parents[3]
```

**Evidence**: 
- `parents[4]` → `.worktrees/task/` (no config/prompts or supervisor)
- `parents[3]` → repo root (has config/prompts and supervisor)

**Impact**: The CLI subprocess tests (Layer 2) would correctly test cross-project asset discovery after this fix.

### Issue 2: Tautological assertions (MINOR)

**Location**: Lines 310, 354

**Problem**: Assertions compare variables to literal strings they were just assigned. Always pass regardless of test behavior.

**Fix**: Remove or replace with meaningful assertions:
```python
# Lines 310 and 354 - remove these:
assert failure_category == "install_missing: prompts (using bundled fallback)"
assert failure_category == "install_missing: supervisor (using bundled fallback)"
```

## Reference

- Audit report: `docs/reports/issue-1928-audit-report.md`
- Execution report: `docs/reports/issue-1928-execution-report.md`

## Verification

After fixing:
1. Run tests: `uv run pytest tests/vibe3/integration/test_cross_project_prompt_smoke.py -v`
2. Verify tests now test global asset discovery (not just bundled fallback)
