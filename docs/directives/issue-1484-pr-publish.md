# PR Publish Directive: Issue #1484 — Epic Lifecycle Check

## Context

**Issue**: #1484 - feat(governance): assignee-pool 应检测 roadmap/epic 子 issue 全部完成后自动关闭 epic

**Status**: MINOR fix completed and verified, ready for PR creation

**Branch**: task/issue-1484

## PR Creation Instructions

### 1. Commit Verification

Ensure commits are present on the branch:
```bash
git log --oneline -3
# Should show commits related to Epic lifecycle check
```

### 2. Push to Remote

```bash
git push origin task/issue-1484
```

### 3. Create Pull Request

**PR Title**:
```
feat(governance): add Epic lifecycle check to assignee-pool governance
```

**PR Body**:
```markdown
## Summary

Add Epic lifecycle check to assignee-pool governance to automatically detect completed epics and suggest their closure.

**Changes**:
- Added Step 6: Epic 收口检查 to governance_scan()
- Query all `roadmap/epic` issues and check sub-issues completion status
- Suggest closing completed epics via `[governance suggest]` comment
- Added deduplication rule to avoid duplicate suggestions
- Updated Intake Decision Flow diagram
- Documented hard boundary exception for epic closure check (lines 21, 236)

**Implementation Details**:
- Epic is considered complete when all sub-issues are closed
- Uses existing `gh issue view` and `gh issue list` commands
- Adds `[governance suggest]` marker to comment for filtering
- Suggests epic closure without triage or label changes

**Files Changed**:
- `supervisor/governance/assignee-pool.md` (documentation updates)
- `docs/directives/issue-1484-*.md` (process documentation)

## Test Plan

- [x] Verify Step 6 logic: query, parse, detect completion
- [x] Verify edge cases: no sub-issues, partial completion
- [x] Verify deduplication: avoid duplicate suggestions
- [x] Verify label safety: no automatic label changes
- [x] Verify template consistency: `[governance suggest]` marker present
- [x] Verify hard boundary documentation: exceptions clearly noted

## Risk Assessment

- **Risk Level**: Low
- **Scope**: Governance material only (no runtime code changes)
- **Impact**: Improved automation for epic lifecycle management
- **Rollback**: Simple git revert if needed

Closes #1484

🤖 Generated with [Claude Code](https://claude.com/claude-code)
```

### 4. Verify PR Creation

After creating PR:
```bash
gh pr view --web
```

Verify:
- PR title and description match the issue scope
- All commits are included
- CI checks start running
- PR is linked to issue #1484

## Quality Requirements

Before marking as done:
- ✅ PR title clearly describes the feature
- ✅ PR body includes summary, changes, test plan, risk assessment
- ✅ PR is linked to issue #1484
- ✅ CI checks are running (expected to pass: governance material only)

## Next Steps After PR Creation

Once PR is created:
1. Update `pr_ref` in handoff with PR URL
2. Manager will verify PR quality and CI status
3. If all checks pass, transition to `state/done`
4. Wait for human review and merge
