# Execution Directive: issue-2135

## Task Summary

Execute plan to refactor orchestra module imports: replace 46 submodule imports with public API imports across 9 files. Add MAX_INTENTS_PER_TICK to orchestra's public interface.

## Plan Reference

**Plan file**: docs/plans/issue-2135-orchestra-public-interface.md

**Key changes**:
1. Update orchestra/__init__.py:
   - Add MAX_INTENTS_PER_TICK to TYPE_CHECKING, __getattr__, __all__
   - Fix module-level imports (2 changes)
   - Fix TYPE_CHECKING imports (5 changes)
   - Fix __getattr__ lazy imports (8 changes)

2. Fix 9 orchestra files:
   - dispatch_coordinator_factory.py (13 fixes)
   - queue_operations.py (13 fixes)
   - queue_persistence_service.py (8 fixes)
   - issue_loader.py (4 fixes)
   - dispatch_health_check.py (3 fixes)
   - protocols.py (2 fixes)
   - logging.py (1 fix)
   - queue_entry.py (1 fix)
   - global_dispatch_coordinator.py (1 fix)

## Scope Boundary

ALLOWED: Modify files in src/vibe3/orchestra/ (including __init__.py), pure import refactoring only
FORBIDDEN: Modify files outside orchestra/, change behavior/logic, modify other modules' public APIs

## Implementation Order

1. Update orchestra/__init__.py first
2. Fix adapter shells (logging.py, queue_entry.py, global_dispatch_coordinator.py)
3. Fix core service files (dispatch_health_check.py, issue_loader.py, protocols.py, queue_operations.py)
4. Fix remaining files (dispatch_coordinator_factory.py, queue_persistence_service.py)

## Validation

After each step: uv run python -c "from vibe3.orchestra import ..."
Final: uv run pytest tests/vibe3/orchestra/ tests/vibe3/test_modularity/ tests/vibe3/domain/test_no_orchestra_imports.py -q

## Expected Outcome

All 46 violations fixed, tests pass, modularity tests confirm compliance.

## Deliverables

Modified: 10 files in src/vibe3/orchestra/
Report: docs/reports/issue-2135-execution-report.md
