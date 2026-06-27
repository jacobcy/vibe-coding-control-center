# Handoff Indicate: Issue #3189 — Publish Instructions

## Status
- Review VERDICT: MINOR (PASSED with minor notes)
- State: merge-ready → executor publish path
- System improvement issue #3199 created (unrelated to current PR)

## PR Publishing Instructions

1. Fix stale comment in `src/vibe3/models/flow.py:95-96,250-251`
   - Replace `# "failed" removed (migrated to "active" or use blocked_reason field).`
   - With: `# "review" and "failed" are valid flow-level statuses for terminal states.`
2. Create PR with title: `fix(task-status): expand flow status support for review/failed/aborted states`
3. Link PR to issue #3189
4. In PR description, note the scope deviation:
   - Plan prohibited modifying `FlowStatusResponse` model
   - Required for Pydantic validation to accept new status values at runtime
5. Ensure CI passes before marking PR ready

## Verification
- All existing tests must pass
- Runtime verification: `vibe3 task status` should show review/failed/aborted flows correctly