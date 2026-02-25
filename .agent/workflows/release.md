---
description: Automated Release Workflow
---

# Release Workflow

## 1. Prerequisites (前置准备)
- [ ] Context gathered: Check git status, ensure clean working directory.
- [ ] Rules loaded: `coding-standards.md`, `patterns.md`.

## 2. Standards Check (规范检查)
**CRITICAL**: 执行前请复核以下规则：
// turbo
cat .agent/rules/coding-standards.md .agent/rules/patterns.md

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

### 3.2 Create Release (自动发布)
使用 `bump_version.sh` 脚本自动处理版本号更新、Changelog 更新和 Git Tag。

```bash
# 升级补丁版本 (Patch): 1.0.0 -> 1.0.1
./.agent/lib/bump_version.sh patch

# 升级次版本 (Minor): 1.0.0 -> 1.1.0
# ./.agent/lib/bump_version.sh minor

# 升级主版本 (Major): 1.0.0 -> 2.0.0
# ./.agent/lib/bump_version.sh major

# 脚本会自动执行:
# 1. 更新 VERSION 文件
# 2. 更新 CHANGELOG.md
# 3. 提示确认
# 4. 提供后续 git 命令指导
```

### 3.3 Commit & Push
脚本执行完毕后，手动提交更改并推送 Tag。

```bash
# 获取新版本号
VERSION=$(cat VERSION)

# 提交更改
git add VERSION CHANGELOG.md
git commit -m "chore(release): bump version to $VERSION"

# 打标签
git tag "v$VERSION"

# 推送
git push origin main
git push origin "v$VERSION"
```

## 4. Verification (验证)
- [ ] Verify tag exists.
```bash
git tag --list | head -n 5
```
- [ ] Verify GitHub Release workflow triggered (optional).
