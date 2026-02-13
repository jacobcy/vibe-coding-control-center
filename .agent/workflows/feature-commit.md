---
description: Interactive Smart Commit Workflow
---

# Feature Commit

## 1. Prerequisites (前置准备)
- [ ] Context gathered: Check current branch.
- [ ] Rules loaded: `git-rules.md`.

## 2. Standards Check (规范检查)
**CRITICAL**: 执行前请复核以下规则：
// turbo
cat .agent/rules/coding-standards.md .agent/rules/git-rules.md

## 3. Execution (执行)
Execute the smart commit process.
> [!IMPORTANT]
> Ensure your commit message follows Conventional Commits (e.g., `feat: ...`, `fix: ...`).
> DO NOT commit directly to `main`.

// turbo
```bash
if [ -f ".agent/lib/git-ops.sh" ]; then
    source .agent/lib/git-ops.sh
    # Verify we are not on main
    current_branch=$(git rev-parse --abbrev-ref HEAD)
    if [[ "$current_branch" == "main" ]]; then
        echo "❌ Error: Cannot commit directly to main. Please checkout a feature branch."
        exit 1
    fi
    smart_commit
else
    echo "Error: .agent/lib/git-ops.sh not found."
    exit 1
fi
```

## 4. Verification (验证)
- [ ] Verify the commit was created.
```bash
git log -1 --stat
```

