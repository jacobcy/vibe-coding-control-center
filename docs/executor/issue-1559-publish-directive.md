# Issue #1559 Executor Publish Directive

## Context
Manager has completed review transition. Review verdict is PASS with all findings verified.

## Current State
- Issue: #1559
- State: `state/merge-ready`
- Verdict: PASS (review complete and credible)
- Commit: dbbe4200 (already exists, verified clean)
- Tests: 18 passed (manager + prompt manifest)
- Baseline: No structural changes (+0 LOC, +0 files)

## Execution Instructions

### Pre-Flight Check
1. Verify working tree is clean: `git status`
2. Verify commit exists: `git log --oneline -1`
3. Verify tests still pass: `uv run pytest tests/vibe3/roles/test_manager.py tests/vibe3/prompts/test_prompt_manifest.py -v`

### PR Creation
1. **Title**: Must include issue number #1559
   - Suggested: `feat(manager): add explicit restricted directory check in handle_ready()`
2. **Body**: Must reference:
   - Issue: #1559
   - Plan ref: docs/plans/issue-1559-implementation-plan.md
   - Report ref: docs/reports/issue-1559-execution-report.md
   - Audit ref: docs/reports/issue-1559-audit-report.md
3. **Labels**: Automatically inherited from issue (roadmap/p0, priority/8, orchestra-governed)

### Post-Creation
1. Verify PR is created and linked to issue #1559
2. Record `pr_ref` in handoff: `uv run python src/vibe3/cli.py handoff append "PR created: #<pr-number>"`
3. Issue will transition to `state/handoff` for manager's PR review

## Key Files
- Changed: `supervisor/manager.md` (lines 391-405: step 1.5 insertion)
- Tests: `tests/vibe3/roles/test_manager.py`, `tests/vibe3/prompts/test_prompt_manifest.py`

## References
- Plan: docs/plans/issue-1559-implementation-plan.md
- Report: docs/reports/issue-1559-execution-report.md
- Audit: docs/reports/issue-1559-audit-report.md
- Baseline snapshot: 2026-05-28T05-04-14+00-00_task-issue-1559_71ddbaa

## Notes
- No special merge requirements
- No conflicts expected (only governance doc changed)
- Commit message already follows standard format
