---
description: Deep Static Analysis & Agentic Code Review
---

# Code Review Protocol

## 1. Prerequisites (前置准备)
- [ ] Context gathered: Check git status, identify files to review.
- [ ] Rules loaded: `coding-standards.md`, `patterns.md`.

## 2. Standards Check (规范检查)
**CRITICAL**: 执行前请复核以下规则：
// turbo
cat .agent/rules/patterns.md .agent/rules/coding-standards.md

## 3. Execution (执行)
Perform deep code review.
> [!IMPORTANT]
> Focus on Architecture, Idempotency, and Safety.

### 3.1 Automated Audit
// turbo
```bash
if [ -f ".agent/lib/audit.sh" ]; then
    source .agent/lib/audit.sh
    check_code || echo "⚠️  Audit issues found."
else
    echo "Error: .agent/lib/audit.sh not found."
    exit 1
fi
```

### 3.2 Contextual Analysis
// turbo
```bash
# Default to "all" if SCOPE is not set
SCOPE="${SCOPE:-all}"

if [ -f ".agent/lib/git-scope.sh" ]; then
    export SCOPE
    zsh .agent/lib/git-scope.sh
else
    echo "Error: .agent/lib/git-scope.sh not found."
    exit 1
fi
```

### 3.3 Report Generation
Act as a Senior Staff Engineer. Generate a report:
- **Compliance Score**: 0-10.
- **Critical Issues**: Must fix.
- **Suggestions**: Nice to have.

## 4. Verification (验证)
- [ ] Verify issues are resolved (if fixes applied).
