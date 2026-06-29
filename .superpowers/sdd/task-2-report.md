# Task 2 Report: Retire Dead `dependencies` Field from Models & Body Parser

## Status
**DONE**

## Implementation Summary
- **Pydantic Model Updates**:
  - Removed `dependencies` and `dependencies_source` fields from `CoordinationTruth` model in `src/vibe3/models/coordination_truth.py`.
  - Removed corresponding source consistency validation for `dependencies` in `validate_source_consistency`.
  - Removed `dependencies` field from `FlowStateProjection` in `src/vibe3/models/issue_body.py` and updated `is_empty()` to ignore it.
- **Issue Body Parser & Renderer**:
  - Updated `parse_projection` in `src/vibe3/services/issue/body.py` to extract numbers from any legacy `- **Dependencies**:` line and merge them into `blocked_by`. The merged list is deduplicated and sorted.
  - Updated `render_projection` in `src/vibe3/services/issue/body.py` to remove rendering of the dependencies key.
- **Dependency Cleanups**:
  - Cleaned up `src/vibe3/services/flow/blocked_state_io.py` to remove `dependencies` arguments when creating `FlowStateProjection`.
  - Cleaned up `src/vibe3/services/orchestra/coordination.py` where `dependencies` or `dependencies_source` were used for local/remote coordination truth construction.
  - Updated `src/vibe3/domain/qualify_gate_checks.py` to check `truth.blocked_by_issues` instead of the retired `truth.dependencies`.
  - Updated `src/vibe3/services/check/service.py` to check `truth.blocked_by_issues` instead of the retired `truth.dependencies`.
- **Test Suite Updates**:
  - Added TDD test `test_parse_projection_merges_legacy_dependencies` to `tests/vibe3/services/test_blocked_state_service.py` to verify legacy dependencies merge into `blocked_by` and that the `dependencies` attribute is gone.
  - Cleaned up retired dependency assertions and tests in `tests/vibe3/models/test_coordination_truth.py`, `tests/vibe3/models/test_issue_body.py`, `tests/vibe3/services/test_coordination_resolver.py`, `tests/vibe3/services/test_issue_body_service.py`, `tests/vibe3/domain/test_qualify_gate_remote.py`, and `tests/vibe3/services/test_check_service_verify_branch.py`.

## Commits
- `66e24c772` refactor: retire dependencies field and merge legacy dependencies into blocked_by

## Verification Results
- All updated/added tests passed successfully.
