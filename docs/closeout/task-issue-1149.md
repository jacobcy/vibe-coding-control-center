---
actor: manager
phase: merge-ready
branch: task/issue-1149
issue: 1149
---

# Executor Publish Directive

## Task
Execute commit + PR creation for tick_id propagation changes

## Verification Steps Completed
- ✅ All tests passed (12 tests)
- ✅ Type checks passed (mypy)
- ✅ Lint passed (ruff)
- ✅ Audit verdict: PASS
- ✅ Review quality: Trustworthy

## Changes Summary
- 5 files modified, +18 lines
- tick_id parameter added to 6 request builder functions
- 3 dispatch handlers wired with tick_id=event.tick_id
- Backward-compatible defaults (tick_id=0)

## Commit Guidelines
- Commit message should reference issue #1149
- Use conventional commit format: `feat(orchestra): ...`
- Include Co-Authored-By footer

## PR Guidelines
- Title: "feat(orchestra): propagate tick_id through role request builders"
- Reference issue #1149
- Describe changes and verification steps
- Mark as ready for review

## Risk
Low. Pure refactor with backward-compatible defaults. No behavior change.
