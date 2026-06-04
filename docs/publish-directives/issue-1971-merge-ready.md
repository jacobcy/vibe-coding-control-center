# Executor Publish Directive: Issue #1971

## Task
Execute commit and PR creation for issue #1971.

## Branch
- Target: `task/issue-1971`
- Base: `main`

## Changes Summary
- **Files**: `src/vibe3/services/flow_rebuild_usecase.py`, `src/vibe3/services/protocols/__init__.py`, `src/vibe3/services/protocols/flow_protocols.py`
- **Scope**: Break last circular dependency (flow_orchestrator ↔ flow_rebuild) with Protocol-based DI
- **Commits**: 1 commit ready for PR

## Commit Messages
```
refactor(services): break flow_orchestrator ↔ flow_rebuild cycle with Protocol DI

Introduce FlowBootstrapProtocol to eliminate the last length-2 circular
dependency in vibe3.services. FlowRebuildUsecase now depends on a Protocol
instead of the concrete FlowOrchestratorService, with the concrete import
deferred to runtime when needed.

Changes:
- Create services.protocols package with FlowBootstrapProtocol definition
- Replace top-level FlowOrchestratorService import in flow_rebuild_usecase
- Defer concrete import to __init__ body as fallback constructor
- Update type annotations to use Protocol interface

Result: 4 → 0 length-2 cycles (-100%). All services cycles resolved.
```

## PR Title
```
refactor(services): break flow_orchestrator ↔ flow_rebuild cycle with Protocol DI
```

## PR Description
````markdown
## Summary
- Break last length-2 circular dependency (flow_orchestrator_service ↔ flow_rebuild_usecase)
- Introduce FlowBootstrapProtocol for dependency inversion
- Defer concrete import to runtime, eliminate top-level import cycle
- Result: 4 → 0 length-2 cycles (-100%, all services architectural cycles resolved)

## Changes
- **services.protocols package**: New package with FlowBootstrapProtocol definition
- **flow_protocols.py**: Protocol interface matching FlowOrchestratorService.bootstrap_issue_flow signature
- **flow_rebuild_usecase.py**: Replace top-level import with Protocol, defer concrete import to __init__ body

## Architecture Impact
- **Before**: 4 length-2 circular dependencies in vibe3.services
- **After**: 0 length-2 cycles (all resolved)
- **Pattern**: Protocol-based dependency inversion for import cycle breaking

## Verification
- 22/22 tests passed (flow_rebuild_usecase + orchestrator + command)
- Import verification: all 3 modules import without circular errors
- Type check: mypy Success, no issues found
- Lint: ruff All checks passed
- No behavior changes, pure import restructuring

## Technical Details
- Protocol signature matches concrete implementation exactly (line-by-line verified)
- Deferred import preserves runtime behavior via fallback constructor
- Structural subtyping satisfied: all existing tests pass without modification

## Related
- Closes #1971
- Phase 1 (PR #1972): Broken 3 cycles (domain.events, domain.dispatch_coordinator)
- Phase 2 (this PR): Broken last cycle (flow_orchestrator ↔ flow_rebuild)

Contributors:
- Yi Chen
- Claude Sonnet 4.5
````

## PR Options
- Draft: `false`
- Base: `main`
- Labels: Keep existing labels (vibe-task, type/refactor, scope/python, roadmap/p1, tech-debt, priority/7, orchestra-governed)

## Pre-Commit Checklist
- 22/22 tests passed
- Type check clean (mypy)
- Lint check clean (ruff)
- Import verification: no circular errors
- Commit already created: 3992ad8d

## Post-PR Actions
- Monitor CI checks
- Update handoff with `pr_ref` after PR created
- Issue will transition to `state/handoff` after PR creation

## Notes
- Low-risk: pure import restructuring, no behavior changes
- Single commit with clear scope
- All tests pass without modification (structural subtyping)
- Completes issue #1971 Phase 2: all services architectural cycles resolved
