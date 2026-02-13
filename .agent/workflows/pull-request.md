---
description: Create a Pull Request
---

# Create Pull Request

## 1. Prerequisites (前置准备)
- [ ] Context gathered: Check current branch and remote status.
- [ ] Rules loaded: `git-rules.md`.

## 2. Standards Check (规范检查)
**CRITICAL**: 执行前请复核以下规则：
// turbo
cat .agent/rules/git-rules.md

## 3. Execution (执行)
Create the pull request.
> [!IMPORTANT]
> Ensure your branch is up-to-date and all changes are committed and pushed.

// turbo
```bash
if [ -f ".agent/lib/gh-ops.sh" ]; then
    source .agent/lib/gh-ops.sh
    # Ensure branch is pushed
    git push -u origin HEAD
    # Pass --web to open in browser, or omit for CLI creation
    pr_create
else
    echo "Error: .agent/lib/gh-ops.sh not found."
    exit 1
fi
```

## 4. Verification (验证)
- [ ] Verify the PR link is generated.
```bash
gh pr view --web
```

