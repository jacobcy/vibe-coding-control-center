# Executor PR Publishing Directive

## Current State
- **Issue**: #608 系统改进：executor 应在 CI-like 环境验证测试
- **Branch**: task/issue-608
- **Commit**: 35a63718 (already committed)
- **Verdict**: PASS (claude/opus)
- **Phase**: merge-ready → executor publish path

## PR Creation Requirements

### 1. PR Title Format
```
feat(ci): add CI-like environment verification for executor workflow (issue #608)
```

### 2. PR Body Requirements
Must include:
- Reference to issue #608 (use "Closes #608" or "Fixes #608")
- Summary of changes:
  - Added CI-like environment verification tests
  - Updated executor workflow policy
  - Enhanced pre-push hook with CI simulation modes
- Test results:
  - 4/4 CI parity tests PASS
  - mypy type check PASS (274 files)
  - Bash syntax validation PASS
- Impact assessment: LOW risk, 0 core files changed

### 3. PR Creation Process
```bash
# Verify commit exists
git log --oneline -1

# Push branch to remote
git push -u origin task/issue-608

# Create PR using gh CLI
gh pr create --title "feat(ci): add CI-like environment verification for executor workflow (issue #608)" --body "$(cat <<'EOF'
## Summary
Implements CI-like environment verification for executor workflow to ensure tests properly simulate CI environment conditions.

Closes #608

## Changes
- Added CI parity tests in `tests/test_ci_parity.py`
- Updated executor workflow policy `policies/executor-workflow.md`
- Enhanced pre-push hook with CI simulation modes

## Test Results
- ✅ 4/4 CI parity tests PASS (normal + GITHUB_ACTIONS=true)
- ✅ mypy type check PASS (274 files)
- ✅ Bash syntax validation PASS
- ✅ Impact: LOW risk, 0 core files changed

## Verification
Tests verify:
1. Working directory independence (os.chdir() usage)
2. Environment variable detection (GITHUB_ACTIONS)
3. CI simulation modes (strict/relaxed)

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

### 4. Post-PR Creation
After PR is created:
- Verify CI checks are running
- Wait for CI to complete
- If CI passes: Record `pr_ref` in handoff
- If CI fails: Report failure details

## Context from Review

### What Was Approved
- Tests properly verify working directory independence
- Documentation examples corrected to valid methods
- Pre-push hook correctly implements CI simulation modes
- No blocking or major issues

### Minor Observations (Non-blocking)
- Redundant imports in test methods (style)
- Unused fixture parameters (dead code)
- These do not affect correctness

### Pre-existing Issues
- 18 unrelated test failures exist (infrastructure debt from #759)
- NOT introduced by this work
- Should be tracked separately

## Quality Checklist
- [ ] PR title matches format
- [ ] PR body references issue #608
- [ ] PR body includes test results
- [ ] Branch pushed to remote
- [ ] PR created successfully
- [ ] CI checks running
- [ ] pr_ref recorded in handoff
