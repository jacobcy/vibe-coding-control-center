# Publish Directive: Issue #2943

## Issue Context
- **Issue**: #2943 - Redundant Code: Duplicate ContextBuilderError and over-exposed internals
- **Type**: refactor (component: agents)
- **Branch**: task/issue-2943
- **Commit**: 99c8b0fa7

## Summary
Successfully consolidated duplicate error classes and internalized section builders across agent prompt modules. The refactoring eliminates code redundancy and prevents external modules from bypassing the unified `PromptManifest`/`PromptContextBuilder` system.

## Changes Summary
- Added shared `ContextBuilderError` to `vibe3.prompts.exceptions`
- Removed duplicate `ContextBuilderError` from `review_prompt.py`
- Removed dead `PlanContextBuilderError` from `plan_prompt.py`
- Internalized 7 section builders with `_` prefix (4 in review_prompt, 3 in plan_prompt)
- Updated module docstrings to promote `PromptManifest`/`PromptContextBuilder`

## Verification Status
✅ All tests pass (149/149 in agents/)
✅ Type check clean (mypy)
✅ Lint clean (ruff)
✅ VERDICT = PASS

## Follow-up Issues Created
- #2973: 系统改进：review_prompt 测试异常类型精确化 (低优先级)
- #2974: 系统改进：ContextBuilderError 继承层次文档化 (低优先级)

## PR Instructions

### Title Format
```
refactor(agents): consolidate ContextBuilderError and internalize section builders
```

### Body Template
```markdown
## Summary
Consolidates duplicate error classes and internalizes section builders across agent prompt modules.

**Changes:**
- Added shared `ContextBuilderError` to `vibe3.prompts.exceptions`
- Removed duplicate `ContextBuilderError` from `review_prompt.py`
- Removed dead `PlanContextBuilderError` from `plan_prompt.py`
- Internalized 7 section builders with `_` prefix
- Updated module docstrings to promote `PromptManifest`/`PromptContextBuilder`

**Issue**: #2943

## Test plan
- [x] All agent tests pass (149/149)
- [x] Type check clean (mypy)
- [x] Lint clean (ruff)
- [x] No scope violations
- [x] VERDICT = PASS (audit report: docs/reports/issue-2943-audit-report.md)

🤖 Generated with [Claude Code](https://claude.com/claude-code)
```

## Merge Checklist
- [ ] CI passes
- [ ] Human review approval
- [ ] Ready for merge

## Notes
- No API breakage (section builders were only used internally and in tests)
- Dead code removal verified (PlanContextBuilderError had zero references)
- Follow-up issues created for minor documentation improvements
