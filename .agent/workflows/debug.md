---
description: Systematic Debugging Workflow
---

# Debugging Workflow

## 1. Prerequisites (前置准备)
- [ ] Context gathered: Check git status, logs.
- [ ] Rules loaded: `coding-standards.md`.

## 2. Standards Check (规范检查)
**CRITICAL**: 执行前请复核以下规则：
// turbo
cat .agent/rules/coding-standards.md

## 3. Execution (执行)
Follow systematic debugging steps.
> [!IMPORTANT]
> Always create a minimal reproduction script before fixing.

### 3.1 Collect Context
// turbo
```bash
echo "=== Git Status ==="
git status
echo "=== Last Commit ==="
git log -1
# vibe doctor (if available)
```

### 3.2 Reproduce Issue
- Create a reproduction script (e.g., `tests/repro_issue_XXX.sh`).
- Ensure it fails reliably.

### 3.3 Analyze & Fix
- Check logs.
- Propose fix.
- Implement using TDD.

## 4. Verification (验证)
- [ ] Verify reproduction script passes with the fix.
```bash
# ./tests/repro_issue_XXX.sh
```

