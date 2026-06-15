# PR Publishing Directive for Issue #2166

## Context

- Issue: #2166 - feat(policy): introduce PolicyLoader and MaterialLoader runtime boundary
- Commit: 8950862a
- Branch: task/issue-2166
- State: state/merge-ready
- Verdict: PASS

## PR Creation Instructions

### Title
```
feat(policy): introduce PolicyLoader and MaterialLoader runtime boundary
```

### Body Template
```
## Summary

Introduce dispatch-time loaders for governance materials and policies, satisfying ADR-0003's dispatch-time material boundary.

**Changes**:
- Add `MaterialLoader` for dispatch-time `.md` file loading with SHA-256 hashes
- Add `PolicyLoader` for dispatch-time `.yaml`/`.yml` policy loading
- Add `resolve_manager_usernames()` helper delegating to config
- Add `MaterialEntry` and `PolicyEntry` frozen Pydantic models
- 25 unit tests covering all functionality (100% pass rate)

**ADR-0003 Compliance**:
- No process-level caching (`@lru_cache` or `@cache`)
- Each `load_all()` call reads from disk (dispatch-time semantics)
- Hash truncation: 16 hex chars for governance material scale

**Test Coverage**:
- Graceful degradation: missing directories, invalid YAML, non-dict YAML
- Hash stability and determinism
- File type filtering and ordering
- Manager username resolution matches `vibe3 status` output (Compatibility mode; `vibe3 task status` is preferred for V3 tasks)

Closes #2166

🤖 Generated with [Claude Code](https://claude.com/claude-code)
```

### PR Metadata
- Base branch: `task/issue-2240` (parent branch for this task)
- Draft: No
- Labels: Already on issue (will be inherited)

## Pre-Publish Verification

Before creating PR, verify:
1. ✅ All commits pushed to remote
2. ✅ No uncommitted changes
3. ✅ Branch is ahead of base branch

## Post-Publish Actions

After PR is created:
1. Record PR number in handoff as `pr_ref`
2. Wait for CI checks to complete
3. If CI fails, transition back to `state/in-progress` with fix instructions
4. If CI passes, transition to `state/done` and close issue

## Notes

- Blocked issues ready for integration: #2167, #2168, #2179
- No process-level caching ensures material hot-reload in development
- Hash truncation (16 chars) sufficient for <100 governance files
