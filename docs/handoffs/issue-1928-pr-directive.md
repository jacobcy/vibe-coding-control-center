# PR Creation Directive for Issue #1928

## Context

- **Issue**: #1928 - test(cross-project): 增加目标 repo 中 plan/run/review/internal manager 的 prompt readiness smoke
- **State**: merge-ready
- **Verdict**: PASS (all findings resolved)
- **Commits**: 
  - 63e1dc5a feat(test): add cross-project prompt readiness smoke tests
  - b7bf417a fix(tests): correct installed_vibe_home fixture asset discovery
  - 67858b1d docs: add fix directive handoff

## PR Requirements

### Title
```
test(cross-project): add cross-project prompt readiness smoke tests (issue #1928)
```

### Description
```markdown
## Summary

Create subprocess-isolated smoke tests that verify plan/run/review/internal manager commands can render prompts via --dry-run --show-prompt without relying on source-tree fallback.

## Changes

- **tests/vibe3/integration/test_cross_project_prompt_smoke.py** (new, 605 lines):
  - Two-layer testing approach (Python-level asset discovery + CLI subprocess smoke tests)
  - Session-scoped `installed_vibe_home` fixture simulating ~/.vibe with runtime assets
  - Function-scoped `target_repo` fixture for cross-project testing
  - Failure categorization helper distinguishing install, flow, prompt, and command issues
  - 10 test cases covering asset discovery, config layering, and CLI flags

## Test Coverage

All 10 tests pass:
- Layer 1: Asset discovery and config layering (5 tests)
- Layer 2: CLI subprocess smoke tests (5 tests)

## Verification

- ✅ All tests pass
- ✅ mypy: no issues
- ✅ ruff: all checks passed
- ✅ black: all checks passed

Fixes #1928
```

## Verification Steps

1. Create PR using vibe-commit or gh pr create
2. Ensure PR title follows conventional commit format
3. Ensure PR description references the issue
4. Run `gh pr checks` to verify CI passes

## Notes

- This is a test-only change (no src/ modifications)
- All acceptance criteria met (see execution report)
- Review verdict: PASS (all findings resolved)
