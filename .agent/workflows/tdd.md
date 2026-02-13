---
description: Test-Driven Development (TDD) Cycle
---

# TDD Workflow

## 1. Prerequisites (前置准备)
- [ ] Context gathered: Identify feature/bug.
- [ ] Rules loaded: `coding-standards.md`.

## 2. Standards Check (规范检查)
**CRITICAL**: 执行前请复核以下规则：
// turbo
cat .agent/rules/coding-standards.md

## 3. Execution (执行)
Implement feature/fix using the TDD cycle.
> [!IMPORTANT]
> **RED-GREEN-REFACTOR**: Never write implementation code before a failing test.

### 3.1 Red Phase (Fail)
- Create/edit test in `tests/`.
- Ensure it FAILS.

### 3.2 Green Phase (Pass)
- Write minimum code to pass the test.
- Run test repeatedly.

### 3.3 Refactor Phase (Clean)
- Optimize code without changing behavior.
- Ensure test still PASSES.

## 4. Verification (验证)
- [ ] Verify all tests pass.
// turbo
```bash
if [ -f "./scripts/test-all.sh" ]; then
    ./scripts/test-all.sh
else
    echo "⚠️  Warning: ./scripts/test-all.sh not found."
fi
```

