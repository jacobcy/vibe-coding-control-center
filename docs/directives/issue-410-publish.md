# Issue #410 Executor Publish Directive

## Context

Review completed with PASS verdict. Issue is transitioning to merge-ready state.

## Implementation Summary

**Feature**: Added `async_execution` config to `OrchestraConfig` for controlling manager dispatch mode.

**Files Modified**:
- `src/vibe3/models/orchestra_config.py`: Added `async_execution: bool = Field(default=True, ...)`
- `src/vibe3/roles/manager.py`: 
  - Added dispatch mode switching logic based on `async_execution`
  - Fixed environment injection bug for both sync and async modes

**Baseline Changes**: +34 LOC, 2 files modified

## Publish Instructions

### Commit Message

```
feat(orchestra): add async_execution config for manager dispatch mode

- Add async_execution: bool field to OrchestraConfig (default=True)
- Support both sync (blocking) and async (tmux) dispatch modes
- Fix environment injection bug for both modes
- Maintain backward compatibility with default=True

Closes #410
```

### PR Title

```
feat(orchestra): add async_execution config for manager dispatch mode
```

### PR Description

```markdown
## Summary

- Added `async_execution: bool` config field to `OrchestraConfig` to control manager dispatch mode
- When `True` (default): manager dispatch runs via tmux (non-blocking, existing behavior)
- When `False`: manager dispatch runs synchronously (blocking, for debugging)
- Fixed environment injection bug that prevented manager token/config vars from being injected in sync mode

## Changes

**OrchestraConfig** (`src/vibe3/models/orchestra_config.py`):
- Added `async_execution: bool = Field(default=True, ...)` field
- Maintains backward compatibility with default=True

**Manager Request Builder** (`src/vibe3/roles/manager.py`):
- Added dispatch mode switching based on `async_execution` config
- Fixed environment variable injection for both sync and async modes:
  - Sync mode: properly initializes `request.env` when None
  - Async mode: properly merges manager-built env vars
- Ensures manager token (`GH_TOKEN`) and backend/model config are injected in both modes

## Testing

- ✅ Unit tests: 3/3 pass (async_execution config tests)
- ✅ Manager tests: 8/8 pass
- ✅ mypy: pass
- ✅ ruff: pass

## Backward Compatibility

- Default value `True` maintains existing async behavior
- No breaking changes to public API
- Config field is additive

## Minor Note

Test coverage gap identified: dispatch behavior and environment injection not covered by integration tests. Recommend adding in future PR (non-blocking).

Closes #410
```

### PR Labels

- `type/feature`
- `priority/medium`
- `roadmap/p1`
- `component/orchestra`

### Draft Status

Create as **ready PR** (not draft) - all tests pass and review completed.

## Quality Checklist

Before creating PR, verify:
- [ ] All tests pass locally
- [ ] mypy passes
- [ ] ruff passes
- [ ] Commit message follows conventional commits format
- [ ] PR description complete and accurate
- [ ] No breaking changes introduced

## Execution Notes

- Use `vibe-commit` skill to commit changes
- Use `gh pr create` to create PR
- PR will be reviewed by human after merge-ready state
- Monitor CI checks after PR creation
