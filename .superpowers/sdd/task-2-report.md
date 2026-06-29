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
- **Review Updates (Post-Review)**:
  - Fixed mock expectations in `tests/vibe3/domain/test_qualify_gate.py` by replacing `mock_truth.dependencies = ...` with `mock_truth.blocked_by_issues = ...` on all mock objects where coordination truth is mocked.
  - Updated the local fallback logic for `blocked_by_issues` in `src/vibe3/services/orchestra/coordination.py` to merge the database dependency links (`self.store.get_dependency_links(branch)`) with the manual `blocked_by_issue` from `flow_state` (if present and not already in the list).
  - Fixed Pydantic ValidationError risk in local fallback logic when `remote_success` is False: updated source fields (`blocked_by_issue_source`, `projection_state_source`, `blocked_reason_source`) in `src/vibe3/services/orchestra/coordination.py` to be robustly set when corresponding fields or `flow_state` exist. Added a unit test to verify this behavior.

## Commits
- `b350ff277` fix(services): robustly set source fields in coordination fallback to prevent validation errors
- `187e77b9e` docs: update task 2 report with coordination fallback merge details
- `65dbed6f6` fix(services): merge database dependency links with local blocked_by_issue in coordination resolver fallback
- `fb715a9d7` docs: update task 2 report with review details
- `1c03007c8` fix(review): resolve mock expectations and update coordination fallback logic for blocked_by_issues
- `66e24c772` refactor: retire dependencies field and merge legacy dependencies into blocked_by

## Verification Results
- Verified that all service tests pass successfully: `uv run pytest tests/vibe3/services/` (919 passed, including `tests/vibe3/services/test_coordination_resolver.py` which now has 4 passed tests).
