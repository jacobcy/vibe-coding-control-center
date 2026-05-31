# Executor Directive: Prepare Commit and PR

## Context

Issue #1682 has completed review with PASS verdict. All architectural violations have been fixed and tests are passing.

## Current State

- **Issue**: #1682 - fix(clients): 修复模块内部违规依赖 config
- **Branch**: task/issue-1682
- **Commit**: 20565596 (refactor(clients): remove internal config dependency via dependency injection)
- **Verdict**: PASS
- **State**: state/merge-ready

## Directive

### 1. Verify Commit Exists

The commit `20565596` should already exist on the branch. Verify:

```bash
git log --oneline -1
```

Expected: `20565596 refactor(clients): remove internal config dependency via dependency injection`

### 2. Push Branch to Remote

```bash
git push -u origin task/issue-1682
```

### 3. Create Pull Request

Create PR with the following details:

**Title**: `fix(clients): 修复模块内部违规依赖 config`

**Body**:
```markdown
## Summary

Fix architectural violation: clients module (Layer 4) was importing config module (Layer 2.5), violating layered architecture.

**Solution**: Dependency injection pattern - clients now accept primitives/instances in constructors, service layer resolves config.

## Changes

- **AIClient**: Accept `api_key`, `model`, `timeout`, `base_url` primitives instead of `AIConfig`
- **AISuggestionClient**: Accept `AIClient | None` instance instead of `AIConfig`
- **GhIssueLabelPort**: Accept `repo: str | None` parameter, no config fallback
- **Service layer**: Resolve config and construct clients explicitly

## Verification

✅ **Architectural compliance**: Zero config imports in clients module
✅ **Test coverage**: 169 client + 21 service/integration tests passing
✅ **Type safety**: mypy success on 36 files
✅ **Caller coverage**: All 5 GhIssueLabelPort call sites updated

## Test Plan

- [x] 169 client tests pass
- [x] 21 service/integration tests pass
- [x] 12 modularity tests pass (4 passed, 7 xfailed, 1 xpassed as expected)
- [x] mypy type checking passes
- [x] No config imports in clients module (`rg "from vibe3.config" src/vibe3/clients/` → no matches)

Fixes #1682

🤖 Generated with [Claude Code](https://claude.com/claude-code)
```

### 4. Record PR Reference

After PR creation, record the PR reference:

```bash
vibe3 handoff pr <pr-number>
```

### 5. Monitor CI Status

Check CI status and wait for all checks to pass:

```bash
gh pr checks <pr-number>
```

If CI fails, report failure and wait for manager decision.

## Success Criteria

- PR created and linked to issue #1682
- PR description matches commit message and audit findings
- CI checks passing (or in progress)
- PR reference recorded in handoff

## Notes

- Improvement issue #1730 created for adding modularity test
- Baseline changes: 6 files modified, +9 LOC, net dependency decrease
- Clean refactoring with no structural concerns
