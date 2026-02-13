{{ ... }}
description: [Short Description of Workflow]
---

# [Workflow Name]

## 1. Prerequisites (前置准备)
- [ ] Context gathered (e.g., `git status`, `git branch`)
- [ ] Rules loaded (读取 `.agent/rules/`)

## 2. Standards Check (规范检查)
**CRITICAL**: 执行前请复核以下规则：
// turbo
cat .agent/rules/coding-standards.md .agent/rules/git-rules.md

## 3. Execution (执行)
[具体的步骤，保留原有的脚本调用逻辑]
> [!IMPORTANT]
> [针对该 Workflow 的核心风险提示]

## 4. Verification (验证)
- [ ] [自动化验证命令]
- [ ] [人工复核项]
