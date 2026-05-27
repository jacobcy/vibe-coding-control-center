# Executor Publish Directive: Issue #1494

## Task
Execute commit and PR creation for issue #1494.

## Branch
- Target: `task/issue-1494`
- Base: `main`

## Changes Summary
- **Files**: `src/vibe3/commands/status.py`, `src/vibe3/commands/status_render.py`, `src/vibe3/services/task_status_classifier.py`, `tests/vibe3/commands/test_task_status_dashboard.py`, `docs/v3/orchestra/task-status-filtering.md`
- **Scope**: Fix Missing State Label classification, complete filtering logic per governance rules, remove Auto Task Scenes
- **Commits**: 3 commits ready for PR

## Commit Messages
```
refactor(cli): fix Missing State Label classification logic and remove Auto Task Scenes

fix(cli): complete task status filtering logic per governance rules

docs: add task status filtering decision tree doc and code references
```

## PR Title
```
fix(cli): split Missing State Label by governed status, complete filtering rules, remove Auto Task Scenes
```

## PR Description
````markdown
## Summary
- Split "Missing State Label" into two sections: Waiting Governance vs Governed Anomaly
- Complete filtering logic: add assignee checks (rules 2/4/5), add Active Exception section
- Remove redundant "Auto Task Scenes" section
- Add decision tree documentation

## Changes
- status.py: Split missing_state into waiting_for_pool and governed_anomaly with assignee filters
- status_render.py: Two-section Missing State rendering + Active Exceptions section
- task_status_classifier.py: New ACTIVE_ANOMALY bucket for active states without assignee
- tests: Updated test fixtures for new output format
- docs/v3/orchestra/task-status-filtering.md: Complete filtering decision tree

## Decision Tree
State label = gate to main flow. No state = never entered. Has state = entered.
Then branch by assignee (rules 2/3/4) and governed status (rules 5/7/8).
Full details: docs/v3/orchestra/task-status-filtering.md

## Verification
- 12/12 task status dashboard tests pass
- mypy strict: no issues
- ruff + black: clean

## Related
- Closes #1494

Contributors:
- Yi Chen
- Claude Sonnet 4.5
````

## PR Options
- Draft: `false`
- Base: `main`
- Labels: Keep existing labels (type/refactor, scope/python, component/cli)

## Pre-Commit Checklist
- 12/12 tests passed
- Type check clean
- Lint check clean
- Copilot review addressed

## Post-PR Actions
- Monitor CI checks
- Update handoff with `pr_ref` after PR created
- Issue will transition to `state/handoff` after PR creation

## Notes
- Medium-risk: changes filtering logic and rendering
- Multiple files changed, includes test updates
- Governance rules documented for future reference
