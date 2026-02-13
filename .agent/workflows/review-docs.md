---
description: Review Documentation and Changelogs
---

# Documentation Review

## 1. Prerequisites (前置准备)
- [ ] Context gathered: Identify documentation changes.
- [ ] Rules loaded: `coding-standards.md`.

## 2. Standards Check (规范检查)
**CRITICAL**: 执行前请复核以下规则：
// turbo
cat .agent/rules/coding-standards.md

## 3. Execution (执行)
Review documentation quality and completeness.
> [!IMPORTANT]
> Ensure `CHANGELOG.md` is updated for all user-facing changes.

### 3.1 Automated Check
// turbo
```bash
if [ -f ".agent/lib/audit.sh" ]; then
    source .agent/lib/audit.sh
    check_docs
else
    echo "Error: .agent/lib/audit.sh not found."
    exit 1
fi
```

### 3.2 Manual Review
- [ ] Is `CHANGELOG.md` updated?
- [ ] Are `docs/` files current?
- [ ] Check for typos and clarity.

## 4. Verification (验证)
- [ ] Verify documentation builds (if applicable) or renders correctly.

