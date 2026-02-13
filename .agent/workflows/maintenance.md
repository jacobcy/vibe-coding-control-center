---
description: Project Maintenance and Cleanup
---

# Project Maintenance

## 1. Prerequisites (前置准备)
- [ ] Context gathered: Check disk usage, temporary files.
- [ ] Rules loaded: `coding-standards.md`.

## 2. Standards Check (规范检查)
**CRITICAL**: 执行前请复核以下规则：
// turbo
cat .agent/rules/coding-standards.md

## 3. Execution (执行)
Perform cleanup and health checks.
> [!IMPORTANT]
> This will delete files in `temp/` and `tmpvibe*`. Ensure no important data is there.

### 3.1 Cleanup
// turbo
```bash
rm -rf temp/*
find . -name "tmpvibe*" -type d -exec rm -rf {} + 2>/dev/null || true
echo "✅ Temp files cleaned."
```

### 3.2 Deep Audit
// turbo
```bash
if [ -f ".agent/lib/audit.sh" ]; then
    source .agent/lib/audit.sh
    check_code
    check_docs
else
    echo "Error: .agent/lib/audit.sh not found."
    exit 1
fi
```

## 4. Verification (验证)
- [ ] Verify clean state.
```bash
ls -A temp/ || echo "temp/ is empty"
```

