# Services Submodule Isolation Progress Tracking

## Objective

Eliminate all cross-module internal imports and achieve complete isolation.

## Baseline (Phase 5 Established)

- **Internal imports count**: 0 (unexpectedly good!)
- **Non-public API imports**: **38 violations**
- **Modules involved**: All 6 submodules
- **High-risk modules**: pr/, task/, issue/

## Progress Tracking

| Phase | Objective | Violations Remaining | Status |
|-------|-----------|----------------------|--------|
| Phase 5 Baseline | Establish tracking mechanism | 38 | ✅ Completed |
| Phase 6 | Eliminate 50% non-public imports | 19 | ⏳ Pending |
| Phase 7 | Eliminate 100% non-public imports | 0 | ⏳ Pending |

## Violation Details (Phase 5 Baseline)

### High Priority (Phase 6)

#### 1. services.pr → services.task
- Violation count: 1
- File: `src/vibe3/services/pr/create.py:15`
- Import: `from vibe3.services.task_binding_guard import ensure_task_issue_bound`
- Strategy: Add `ensure_task_issue_bound` to services.task public API

#### 2. services.pr → services.issue
- Violation count: 1
- File: `src/vibe3/services/pr/resolver.py:11`
- Import: `from vibe3.services.issue_branch_resolver import resolve_issue_branch_input`
- Strategy: Add `resolve_issue_branch_input` to services.issue public API

#### 3. services.issue → services.flow
- Violation count: 1
- File: `src/vibe3/services/issue/failure.py:16`
- Import: `from vibe3.services.flow_timeline_service import FlowTimelineService`
- Strategy: Import via services.flow public API

#### 4. services.shared internal symbols
- Violation count: 7
- Files:
  - `pr/loc_comment.py` - LOCStats
  - `pr/verdict_service.py` - extract_role_from_actor, GitPathProtocol
  - `pr/status_checker.py` - get_git_common_dir
  - `task/show.py` - resolve_ref_path
  - `task/classifier.py` - has_manager_assignee
  - `issue/dispatch_policy.py` - classify_dispatch_eligibility
- Strategy: Add these symbols to services.shared.__init__.py __all__

### Medium Priority (Phase 6)

- Remaining shared/ violations (6 more)

### Low Priority (Phase 7)

- Final cleanup and documentation

## Architecture Test

Test file: `tests/vibe3/architecture/test_service_isolation.py`

Run baseline:
```bash
uv run pytest tests/vibe3/architecture/test_service_isolation.py -v
```

## Next Steps

1. Fix root directory file migration (#2586)
2. Expand services.shared public API to include commonly used internal symbols
3. Fix high-priority violations (Phase 6)
4. Complete Phase 7 elimination