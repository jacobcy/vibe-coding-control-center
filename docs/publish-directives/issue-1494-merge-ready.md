# Executor Publish Directive: Issue #1494

## Task
Execute commit and PR creation for issue #1494.

## Branch
- Target: `task/issue-1494`
- Base: `main`

## Changes Summary
- **File**: `src/vibe3/commands/status_render.py`
- **Scope**: Remove "Auto Task Scenes" section from status display
- **Lines**: -36/+4
- **Commit**: Ready for commit (tests passed, type/lint clean)

## Commit Message
```
refactor(cli): remove Auto Task Scenes from task status display

Simplify status output by consolidating Auto Task Scenes and Manual Scenes
into a single "Active Scenes" section. All active flows now display uniformly
regardless of branch type.

- Remove lazy imports of is_auto_task_branch and is_canonical_task_branch
- Remove split between auto-flows and manual-flows
- Unify rendering under single "Active Scenes" header
- Net reduction: -32 LOC

Closes #1494
```

## PR Title
```
refactor(cli): remove Auto Task Scenes from task status display
```

## PR Description
````markdown
## Summary
- Remove "Auto Task Scenes" section from `vibe3 task status` output
- Consolidate display into single "Active Scenes" section
- Clean refactor with -32 net LOC reduction

## Changes
- Removed lazy imports and rendering logic for auto-task-specific flows
- All active flows now display uniformly under "Active Scenes"
- RFC/Epic/Blocked/Completed sections unchanged (from #1462)

## Verification
- ✅ All 903 tests passed
- ✅ Type check: 0 errors
- ✅ Lint check: 0 errors
- ✅ Manual verification: `vibe3 task status` output correct

## Related
- Implements #1494
- Scope limited to Auto Task Scenes removal only
- RFC/Epic sections from #1462 remain intact

🤖 Generated with [Claude Code](https://claude.com/claude-code)
````

## PR Options
- Draft: `false`
- Base: `main`
- Labels: Keep existing labels (type/refactor, scope/python, component/cli)

## Pre-Commit Checklist
- ✅ All tests passed (903 tests)
- ✅ Type check clean
- ✅ Lint check clean
- ✅ Manual verification successful

## Post-PR Actions
- Monitor CI checks
- Update handoff with `pr_ref` after PR created
- Issue will transition to `state/handoff` after PR creation

## Notes
- Low-risk refactor with minimal impact
- Single file changed, no cross-module dependencies
- Ready for immediate merge after CI passes
