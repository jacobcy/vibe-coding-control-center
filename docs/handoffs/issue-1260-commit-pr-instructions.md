# Commit & PR Instructions — Issue #1260

## Context

**Issue**: #1260 refactor(v3/domain): orchestration_facade.py 完善依赖注入
**Branch**: task/issue-1260
**Verdict**: PASS (MINOR fixes verified)
**Ready for**: Commit + PR creation

## Work Summary

### Core Changes (2 commits)
1. `736b284f` - refactor(domain): eliminate per-tick SQLiteClient + SessionRegistryService creation
   - Added `registry` constructor parameter to OrchestrationFacade
   - Eliminated per-tick instance creation in `on_tick()`
   - Maintained backward compatibility with fallback behavior

2. `71f17f0e` - fix(tests): address MINOR audit findings
   - Reverted out-of-scope test_failed_gate.py modification (restored database cleanup)
   - Added test for injected registry DI path

### Files Modified
- `src/vibe3/domain/orchestration_facade.py` - DI refactoring
- `tests/vibe3/domain/test_orchestration_facade_dispatch.py` - Added DI test
- `tests/vibe3/orchestra/test_failed_gate.py` - Restored cleanup fixture

### Verification
- ✅ All 23 tests pass
- ✅ Type check: mypy SUCCESS
- ✅ Lint: ruff PASSED
- ✅ Backward compatibility: verified
- ✅ No deviations from plan

## Commit Instructions

**Status**: All changes are already committed in 2 commits. No additional commit needed.

If you need to verify:
```bash
git log --oneline -2
git status  # Should be clean
```

## PR Creation Instructions

### PR Title
```
refactor(v3/domain): eliminate per-tick SQLiteClient + SessionRegistryService creation
```

### PR Body
```markdown
## Summary
- Add `registry` constructor parameter to OrchestrationFacade for dependency injection
- Eliminate per-tick SQLiteClient + SessionRegistryService creation in `on_tick()`
- Maintain backward compatibility with fallback behavior
- Add test coverage for injected registry path

Fixes #1260

## Changes
- `src/vibe3/domain/orchestration_facade.py`: DI refactoring (28 lines)
- `tests/vibe3/domain/test_orchestration_facade_dispatch.py`: Added test for DI path (51 lines)
- `tests/vibe3/orchestra/test_failed_gate.py`: Restored database cleanup fixture (16 lines)

## Test Plan
- [x] All 23 tests pass
- [x] Type check: mypy SUCCESS
- [x] Lint: ruff PASSED
- [x] Backward compatibility verified through existing tests
- [x] New test verifies injected registry path

🤖 Generated with [Claude Code](https://claude.com/claude-code)
```

### PR Creation Command
```bash
gh pr create --title "refactor(v3/domain): eliminate per-tick SQLiteClient + SessionRegistryService creation" --body "$(cat <<'EOF'
## Summary
- Add `registry` constructor parameter to OrchestrationFacade for dependency injection
- Eliminate per-tick SQLiteClient + SessionRegistryService creation in `on_tick()`
- Maintain backward compatibility with fallback behavior
- Add test coverage for injected registry path

Fixes #1260

## Changes
- `src/vibe3/domain/orchestration_facade.py`: DI refactoring (28 lines)
- `tests/vibe3/domain/test_orchestration_facade_dispatch.py`: Added test for DI path (51 lines)
- `tests/vibe3/orchestra/test_failed_gate.py`: Restored database cleanup fixture (16 lines)

## Test Plan
- [x] All 23 tests pass
- [x] Type check: mypy SUCCESS
- [x] Lint: ruff PASSED
- [x] Backward compatibility verified through existing tests
- [x] New test verifies injected registry path

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

## Post-PR Creation

After creating PR, executor should:
1. Run `gh pr view <pr-number>` to verify PR was created
2. Record PR reference: `vibe3 handoff pr docs/prs/issue-1260-pr.md` (if needed)
3. State will transition to `state/handoff` for manager final review

## Notes

- The PR title matches the first commit message (conventional commit format)
- PR references the parent issue #1260 with "Fixes #1260" for auto-close on merge
- All verification checks already passed, so CI should pass
- No additional changes needed - ready for merge
