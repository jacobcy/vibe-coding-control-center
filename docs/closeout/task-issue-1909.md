# Publish Directive: Issue #1909

## Task
Create PR for verified policy changes that address issue #1852's root cause.

## Commit & PR Requirements

### Commit Message
- Already created: 06f0aba7
- Message: "feat(policy): add branch identity verification to review process"
- Detailed description included
- Issue reference: #1909

### PR Title
`feat(policy): add branch identity verification to review process`

### PR Description
```
## Summary
- Add branch identity verification to review policies to prevent wrong-branch audits
- Addresses root cause of issue #1852 where audit tool analyzed commits from dev/issue-1851 instead of task/issue-1852
- Policy-only changes (no Python source code modifications)

## Changes
- **review.md**: Added step 0.5 "分支身份验证" requiring git branch/log verification before review
- **common.md**: Added branch consistency commands in "做 review 前" section
- **run.md**: Added executor defensive verification step 0 for repair directive validation

## Verification
✅ All 20 review-related tests pass
✅ Policy file readable by prompt builder (7051 chars)
✅ No scope violations (policy-only changes)

## Testing
```bash
# Run review policy tests
uv run pytest tests/vibe3/agents/test_review_prompt.py -q

# Verify policy readability
uv run python -c "from vibe3.agents.review_prompt import build_policy_section; from vibe3.services.convention_resolver import ConventionResolver; resolver = ConventionResolver.from_repo(); policy_path = resolver.get_policy_path('review'); content = build_policy_section(policy_path); print(len(content), 'chars')"
```

Closes #1909
```

## Quality Checklist
- [x] Commit message clear and descriptive
- [x] PR title follows convention
- [x] PR description includes summary, changes, verification, and testing sections
- [x] Issue reference included
- [x] No CI failures expected (policy-only changes)

## After PR Creation
- PR will transition issue to `state/handoff`
- Manager will verify PR quality and CI status
- Issue will move to `state/done` after PR approval

## Notes
- Review passed with minor note: review.md +47 lines exceeds plan guideline but well-structured
- No structural changes detected (policy-only modifications)
- Ready for immediate PR creation
