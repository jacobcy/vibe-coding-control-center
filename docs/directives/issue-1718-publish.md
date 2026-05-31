# Publish Directive: Issue #1718

## Context

- **Issue**: #1718 - refactor(api): CLI 与服务层公共接口统一（commands + server）
- **Branch**: task/issue-1718
- **Commit**: 1303ca9d
- **Verdict**: MINOR (review passed with notes)
- **Improvement Issue**: #1754

## Review Summary

重构正确执行，所有验证通过：
- ✅ 308 tests passed (commands 298 + server 10)
- ✅ mypy 0 errors
- ✅ ruff all passed
- ✅ 3 cross-package import violations eliminated

## MINOR Finding

发现脆弱循环依赖：`server/registry.py` 通过 `from vibe3.server import ...` 导入父包 re-export。

**建议**：在 PR 描述中说明此问题并链接改进 issue #1754。

## Publishing Instructions

### 1. Verify Commit
```bash
git log --oneline -1
# Should show: 1303ca9d refactor(api): unify public interfaces in commands and server modules
```

### 2. Push Branch
```bash
git push -u origin task/issue-1718
```

### 3. Create Pull Request

**Title**:
```
refactor(api): unify public interfaces in commands and server modules
```

**Body**:
```markdown
## Summary
- Eliminate 3 cross-package import violations in commands and server modules
- commands/status.py: import from vibe3.commands instead of vibe3.server
- server/registry.py: import from vibe3.server instead of vibe3.domain/runtime
- Add re-exports in commands/__init__.py and server/__init__.py

## Changes
- `src/vibe3/commands/__init__.py`: Add _validate_pid_file re-export
- `src/vibe3/commands/status.py`: Update import path
- `src/vibe3/server/__init__.py`: Add FailedGate/FlowManager/CircuitBreaker/HeartbeatServer re-exports
- `src/vibe3/server/registry.py`: Update import paths

## Verification
- ✅ 308 tests passed (commands 298 + server 10)
- ✅ mypy 0 errors
- ✅ ruff all passed
- ✅ Fresh import succeeds (circular parent-package import documented below)
- ✅ No stale references remaining (grep confirmed)

## Known Issues
⚠️ **Fragile Import Pattern**: server/registry.py imports from parent package (vibe3.server), creating circular dependency relying on import order.

**Impact**: Current code works correctly, but future maintenance that reorders imports in __init__.py could break this.

**Follow-up**: Issue #1754 created to address this fragility.

Fixes #1718
```

### 4. Post-PR Actions
- Verify PR created successfully
- Wait for CI checks to pass
- Link improvement issue #1754 in PR

## Expected Outcome
- PR created on branch task/issue-1718
- CI passes (tests, mypy, ruff)
- Ready for human review and merge
