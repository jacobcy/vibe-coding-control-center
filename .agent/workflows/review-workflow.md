---
description: Review and Optimize an existing Workflow file
---

# Workflow Audit Protocol

## 1. Prerequisites (前置准备)
- [ ] Context gathered: List available workflows.
- [ ] Rules loaded: `architecture.md`, `templates/workflow.md`.

## 2. Standards Check (规范检查)
**CRITICAL**: 执行前请复核以下规则：
// turbo
cat .agent/rules/architecture.md .agent/templates/workflow.md

## 3. Execution (执行)
Audit and improve a workflow file.
> [!IMPORTANT]
> Ensure all workflows follow the `_template.md` structure strictly.

### 3.1 Target Selection
// turbo
```bash
echo "=== Select Workflow to Review ==="
ls .agent/workflows/*.md
# read -p "Enter workflow filename (e.g., my-flow.md): " target_flow
# target_path=".agent/workflows/$target_flow"
```

### 3.2 Structural Audit
Review `$target_path` against `_template.md`.
Check for:
1.  **Prerequisites**: Context and Rules.
2.  **Standards Check**: `cat .agent/rules/...`
3.  **Execution**: Clear steps and alerts.
4.  **Verification**: Explicit check.

### 3.3 Quality Report & Optimization
Generate a report and offer to fix issues.

## 4. Verification (验证)
- [ ] Verify the optimized workflow matches the template.

