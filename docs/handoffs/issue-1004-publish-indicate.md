# Publish Indicate — Issue #1004

**Branch**: task/issue-1004
**Issue**: #1004 — 测试审查: services 模块 (60个测试文件) - 消除重复与冗余

## Action
Execute commit + PR creation (vibe-commit skill).

## Context
- Review VERDICT: PASS (trusted audit)
- Net change: 3 test files deleted, new tests added, -134 LOC
  - Deleted: test_issue_failure_refactored.py, test_pr_create_usecase.py, test_flow_status_resolver.py
  - Added: test_expired_resource_cleanup_service.py (new module)
  - Relocated: tests moved between files for better organization
- 420 tests passing, coverage 68% maintained
- Baseline structural diff: stable (no major module/dependency changes)

## Notes
- Deferred work (Steps 8-16: remaining merges + parameterization) can be done in future iterations
- Coverage 68% acceptable (individual service modules 80%+)
- Code quality good, merged tests clear and maintainable
- Risk: LOW — test deduplication only, no functional code changes

## Requirements
- PR description should reflect test deduplication refactor
- Ensure PR description lists:
  - Files deleted: test_issue_failure_refactored.py, test_pr_create_usecase.py, test_flow_status_resolver.py
  - Files added: test_expired_resource_cleanup_service.py
  - Tests relocated: FlowStatusResolver → test_flow_status.py, clean_residual_branches → test_check_cleanup_service.py
  - Net LOC reduction: -134 lines
  - Deferred work rationale
- Mention that core test coverage maintained, all 420 tests pass