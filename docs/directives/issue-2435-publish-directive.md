# Publish Directive: Issue #2435 - Create PR

## Status
Review PASSED - Ready for merge

## Summary
Fixed --model parameter passing bug and CLI validation issue across all command paths.

## Implementation
- **Initial commit**: 8de1f0f3 - Fix --model parameter passing and CLI validation (15 files, +126/-15)
- **Fix commit**: 8668e872 - Move model validation after config loading (4 files, +60/-35)

## Changes Overview
1. CLI validation for --model without --backend (from CLI or config)
2. Fixed parameter passing in all code paths
3. Unified output format across Plan/Run/Review/Manager roles
4. Resolved MAJOR validation gate bug

## Test Results
- Initial: 536 tests pass
- Fix: 403 command tests pass, 71 affected tests pass
- Type checking (mypy) passes
- Linting (ruff) passes

## PR Requirements
- Title: fix(cli): --model parameter passing and CLI validation
- Body should include:
  - Bug description and root cause
  - Fix implementation details (Part A + Part B)
  - MAJOR fix explanation
  - Test verification results
  - Scope summary

## References
- Plan: docs/plans/issue-2435-implementation-plan.md
- Initial report: docs/reports/issue-2435-execution-report.md
- Fix report: docs/reports/issue-2435-execution-report-fix.md
- Initial audit: docs/reports/issue-2435-audit-report.md (MAJOR)
- Retry audit: docs/reports/issue-2435-audit-report-retry.md (PASS)

## Notes
- Two commits on branch (initial + fix)
- All tests verified passing
- Ready for merge after PR creation
