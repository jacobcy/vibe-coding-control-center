# Publish Instructions: Issue #3183

## Review Status
- Verdict: MINOR (3 minor doc inaccuracies found, does not block merge)
- Reviewer found no MAJOR/BLOCK issues

## Minor fixes needed (recommended before PR)
The audit found 3 minor inaccuracies in the READMEs:

1. **shared/README.md — symbol count**: Says 55, actual `__all__` is 50. Fix the total and category subtotals.
2. **orchestra/README.md — file/error counts**: "12 files" should be "10 files" (or clarify __init__.py); "3 个" error handlers should be "4 个".
3. **shared/README.md — LOC/file count scope**: 3,381 LOC includes __init__.py but file count (22) excludes it. Make consistent (23 files/3,381 LOC or 22 files/3,146 LOC).

These are optional pre-PR cleanup — the reviewer stated they "do not block merge."

## Follow-up issue (REQUIRED per human instruction)
The planner found 19 dead exports + anti-patterns in services submodules (recorded in handoff findings). Per @jacobcy's instructions, create a follow-up GitHub issue following the PR #3195 → #3198 pattern.

Dead exports found:
- services/shared: 17 symbols with 0 external package-level imports
- services/orchestra: 2 passthrough re-exports from config
- services/protocols: 1 anti-pattern (TYPE_CHECKING-only imports, no __getattr__ lazy import)

## Commit + PR
1. Apply the 3 minor fixes if you choose (recommended but not blocking)
2. Commit with conventional commit format
3. Create PR with `Fixes #3183`
4. Verify CI passes

## PR description should include
- Summary of created READMEs (3 files)
- Reference to planned follow-up issue for dead exports
- Note about MINOR audit findings