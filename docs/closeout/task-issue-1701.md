# Closeout Directive: task/issue-1701

## Context
- Issue: #1701 - 系统改进：executor 验证范围应覆盖受影响的测试目录
- Branch: task/issue-1701
- State: merge-ready
- Verdict: PASS

## PR Creation Instructions

### Commit Guidelines
- Commit already exists: b576edee
- Message: "feat(prompts): improve executor test scope verification"
- Changes:
  - config/prompts/prompts.yaml (test scope guidance)
  - supervisor/policies/run.md (test scope selection)

### PR Requirements
1. **Title**: "feat(prompts): improve executor test scope verification"
2. **Body Structure**:
   - Summary: Add test scope selection guidance to executor prompts and policies
   - Changes: List modified files and key additions
   - Testing: Reference verification steps from execution report
   - Issue: Closes #1701
3. **Labels**: Will inherit from issue (vibe-task, roadmap/p1, priority/5)
4. **Base**: main

### Key Points to Emphasize
- This is an additive change (no breaking changes)
- Only prompt/policy modifications, no code changes
- Aligns with existing pre_push_test_selector implementation
- All verification steps passed (YAML valid, prompt assembly OK, CLI working)

## Post-PR Actions
- Update flow with pr_ref after PR creation
- Monitor CI status
- Wait for human review and merge
