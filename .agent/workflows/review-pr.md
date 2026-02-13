---
description: Review Pull Requests
---

# PR Review Protocol

## 1. Prerequisites (前置准备)
- [ ] Context gathered: List open PRs.
- [ ] Rules loaded: `git-rules.md`, `coding-standards.md`.

## 2. Standards Check (规范检查)
**CRITICAL**: 执行前请复核以下规则：
// turbo
cat .agent/rules/git-rules.md .agent/rules/coding-standards.md

## 3. Execution (执行)
Review a Pull Request.
> [!IMPORTANT]
> Be constructive and specific.

### 3.1 List PRs
// turbo
```bash
if [ -f ".agent/lib/gh-ops.sh" ]; then
    source .agent/lib/gh-ops.sh
    pr_review_list
else
    echo "Error: .agent/lib/gh-ops.sh not found."
    exit 1
fi
```

### 3.2 Review Process
1.  **Checkout**: `gh pr checkout <PR_NUMBER>`
2.  **Diff**: `gh pr diff <PR_NUMBER>`
3.  **Checklist**:
    - [ ] Architecture
    - [ ] Security
    - [ ] Standards
    - [ ] Docs/Tests

### 3.3 Submit Feedback
- **Request Changes**: `gh pr review <PR> --request-changes --body "..."`
- **Approve**: `gh pr review <PR> --approve --body "LGTM"`
- **Comment**: `gh pr review <PR> --comment --body "..."`

## 4. Verification (验证)
- [ ] Verify review status.
```bash
# gh pr view <PR>
```

