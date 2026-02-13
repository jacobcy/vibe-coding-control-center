---
description: Automated Release Workflow
---

# Release Workflow

## 1. Prerequisites (前置准备)
- [ ] Context gathered: Check git status, ensure clean working directory.
- [ ] Rules loaded: `git-rules.md`.

## 2. Standards Check (规范检查)
**CRITICAL**: 执行前请复核以下规则：
// turbo
cat .agent/rules/coding-standards.md .agent/rules/git-rules.md

## 3. Execution (执行)
Perform release steps.
> [!IMPORTANT]
> **IRREVERSIBLE ACTION**: Tagging and pushing a release is permanent. Ensure all tests pass.

### 3.1 Pre-release Checks
// turbo
```bash
# Ensure clean state
if [ -n "$(git status --porcelain)" ]; then
    echo "❌ Error: Working directory not clean."
    exit 1
fi
# Run tests
if [ -f "./scripts/test-all.sh" ]; then
    ./scripts/test-all.sh
else
    echo "⚠️  Warning: ./scripts/test-all.sh not found. Skipping tests."
fi
```

### 3.2 Create Release
```bash
# VERSION="v0.x.x"
# git tag -a $VERSION -m "Release $VERSION"
# git push origin $VERSION
```

## 4. Verification (验证)
- [ ] Verify tag exists.
```bash
git tag --list | head -n 5
```

