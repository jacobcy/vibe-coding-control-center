# PR Publishing Directive - Issue #2402

## Context

- **Issue**: #2402 - Filter-Instead-of-Delete: github_issues_ops over-fetching in view_issue
- **Commit**: 764dbace - refactor(clients): add fields parameter to view_issue to eliminate over-fetching
- **Branch**: task/issue-2402
- **State**: merge-ready
- **Verdict**: MINOR (dead code addressed via follow-up #2423)

## Implementation Summary

Successfully added optional `fields` parameter to `view_issue` method to eliminate over-fetching:
- Default excludes expensive `comments` field
- Updated 3 callers needing comments to explicitly request it
- Updated `get_issue_body` and `close_issue_if_open` for minimal requests
- All 237 tests pass
- mypy/ruff clean
- Backward compatible

## PR Requirements

### Title Format
```
refactor(clients): add fields parameter to view_issue to eliminate over-fetching
```

### Description Template
```markdown
## Summary

Add optional `fields` parameter to `view_issue` method to eliminate over-fetching of GitHub issue data. Default excludes the expensive `comments` field, reducing API payload size for callers that don't need comments.

Addresses code-auditor finding: Filter-Instead-of-Delete over-fetching pattern in `github_issues_ops.py:243-263`.

## Changes

- **`view_issue`**: Add `fields: list[str] | None = None` parameter with default excluding `comments`
- **`get_issue_body`**: Request minimal `fields=["body"]`
- **`close_issue_if_open`**: Request minimal `fields=["state"]`
- **Updated callers needing comments**:
  - `flow_status_resolver.py`: `fields=["body", "comments"]`
  - `flow_timeline_service.py`: `fields=["comments"]`
  - `task/show.py`: full fields including `comments`

## Performance Impact

Eliminates over-fetching for 13 callers that don't need `comments`:
- `comments` field is typically the largest field in issue data
- API calls now more efficient with smaller payloads

## Test Coverage

- Added tests for custom/default fields parameter
- Updated tests to verify parameter propagation
- All 237 tests pass
- Type checking clean (mypy)
- Linting clean (ruff)

## Backward Compatibility

✅ Fully backward compatible:
- Optional parameter with sensible default
- Default field set covers all fields accessed by existing callers
- No breaking changes to existing code

## Follow-up

Minor finding: duplicate `_DEFAULT_VIEW_FIELDS` constant (dead code on line 70)
- Tracked in #2423
- No functional impact
- Can be removed in follow-up PR

Closes #2402

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
```

## PR Metadata

- **Base branch**: `main`
- **Labels**: Apply appropriate labels (refactor, clients)
- **Assignees**: Already assigned
- **Reviewers**: No additional reviewers needed (automation complete)

## Pre-merge Checklist

Executor should verify before final merge:
- ✅ All tests pass
- ✅ Commit message follows standards
- ✅ No merge conflicts with main
- ✅ CI checks pass (if configured)

## Notes

- MINOR verdict handled via follow-up issue #2423
- Core implementation is correct and complete
- No urgent issues blocking merge
- Ready for final human review and merge