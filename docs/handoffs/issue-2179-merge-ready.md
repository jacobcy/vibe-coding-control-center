# Publish Indicate — Issue #2179

**Branch**: task/issue-2179
**Issue**: #2179 — Roundabout Logic: Misplaced global metric calculation in _diff_files

## Action
Execute commit + PR creation (vibe-commit skill).

## Context
- Review VERDICT: PASS (trusted audit)
- Commit: 7eba599c refactor(analysis): move global metric calculation to compute_diff
- Net change: 1 file modified, +1 LOC (pure refactor)
- Change: Moved `total_loc_delta` and `total_functions_delta` from `_diff_files` to `compute_diff`
- 139 tests passing (136 analysis + 3 snapshot model)
- Type checking: PASS (mypy)
- Linting: PASS (ruff)
- Baseline structural diff: minimal (no new modules/dependencies/functions)

## Notes
- Pure refactor, no functional changes
- Placement after `DiffSummary.__add__` is correct and preserves values
- Downstream consumers validated (snapshot_diff_section.py, snapshot.py)
- Risk: LOW — code movement only, all tests pass

## Requirements
- PR title: `refactor(analysis): move global metric calculation to compute_diff`
- PR description should explain:
  - This is a pure refactor moving global metrics to the correct location
  - `total_loc_delta` and `total_functions_delta` moved from `_diff_files` to `compute_diff`
  - No functional changes, all tests pass (139 tests)
  - Type checking and linting pass
- Link to issue #2179
- Target branch: main
