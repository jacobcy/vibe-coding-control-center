# PR Publishing Directive: Issue #1705

## Task Summary

Issue #1705 completed a revert of incorrect mock path changes. The second-round audit verified all changes are correct and tests pass.

## Current State

- **Branch**: task/issue-1705
- **Commit**: 83c0196f (revert commit)
- **Verdict**: PASS (Round 2 Audit)
- **Status**: Ready for PR creation

## Audit Summary

The first execution changed mock paths to use public API, but the first audit (MAJOR) found this was incorrect because production code imports from the internal path `vibe3.agents.backends.codeagent`, not the public API.

The second execution reverted all 4 mock path changes back to the correct internal path:
- `tests/vibe3/commands/test_flow_update.py:130`
- `tests/vibe3/domain/handlers/test_governance_scan.py:14`
- `tests/vibe3/services/test_check_cleanup_service.py:107`
- `tests/vibe3/services/test_check_cleanup_service.py:135`

All tests pass (35/35), lint is clean, and no residual incorrect paths remain.

## PR Requirements

### Title
```
revert(tests): restore correct mock paths for CodeagentBackend
```

### Description Must Include

1. **Context**: Briefly explain that the first attempt to unify mock paths was incorrect
2. **Problem**: Production code imports from internal path, not public API
3. **Solution**: Reverted 4 mock paths to match production imports
4. **Verification**: All tests pass, no residual incorrect paths
5. **References**:
   - Audit report: `docs/reports/issue-1705-audit-round2.md`
   - System improvement issue: #1767

### Example Description

```markdown
## Summary
Reverts incorrect mock path changes from commit 4ced50b9.

## Problem
The first execution changed mock paths from `vibe3.agents.backends.codeagent.CodeagentBackend` to `vibe3.agents.CodeagentBackend`, assuming production code uses the public API.

However, all 16+ production import sites use the internal path:
```python
from vibe3.agents.backends.codeagent import CodeagentBackend
```

With `unittest.mock.patch`, these paths are not equivalent for late imports. The old path was correct.

## Solution
Reverted all 4 mock paths to the correct internal path:
- `tests/vibe3/commands/test_flow_update.py:130`
- `tests/vibe3/domain/handlers/test_governance_scan.py:14`
- `tests/vibe3/services/test_check_cleanup_service.py:107, 135`

## Verification
- ✅ All tests pass (35/35)
- ✅ Lint clean
- ✅ No residual incorrect paths

## References
- Audit: docs/reports/issue-1705-audit-round2.md
- System improvement: #1767 (decorative mocks and additional mock path review)

Closes #1705
```

## Pre-PR Checklist

Before creating PR, ensure:
- [ ] All tests pass: `uv run pytest tests/vibe3/commands/test_flow_update.py tests/vibe3/domain/handlers/test_governance_scan.py tests/vibe3/services/test_check_cleanup_service.py -v`
- [ ] Lint passes: `uv run ruff check tests/`
- [ ] No incorrect mock paths remain: `grep -r "patch.*vibe3.agents.CodeagentBackend" tests/`

## Post-PR Actions

After PR is created:
1. Monitor CI status
2. If CI fails, check logs and fix issues
3. PR should be ready for human review

## Notes

- This is a pure revert with no logic changes
- The issue scope is complete (4 mock paths reverted)
- System improvement issue #1767 tracks follow-up work on decorative mocks
