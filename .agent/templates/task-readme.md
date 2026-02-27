---
task_id: "{{TASK_ID}}"
title: "{{TASK_TITLE}}"
created: "{{DATE}}T00:00:00Z"
updated: "{{DATE}}T00:00:00Z"
current_layer: "prd"
status: "draft"

gates:
  scope:
    status: "pending"
    timestamp: ""
    reason: ""
  spec:
    status: "pending"
    timestamp: ""
    reason: ""
  plan:
    status: "pending"
    timestamp: ""
    reason: ""
  test:
    status: "pending"
    timestamp: ""
    reason: ""
  code:
    status: "pending"
    timestamp: ""
    reason: ""
  audit:
    status: "pending"
    timestamp: ""
    reason: ""
---

# Task: {{TASK_TITLE}}

## 概述

[任务描述]

## 当前状态

- **层级**: PRD（认知层）
- **状态**: Draft
- **最后更新**: {{DATE}}

## Gate 进展

| Gate | 状态 | 时间 | 备注 |
|------|------|------|------|
| Scope Gate | ⏳ Pending | - | |
| Spec Gate | ⏳ Pending | - | |
| Plan Gate | ⏳ Pending | - | |
| Test Gate | ⏳ Pending | - | |
| Code Gate | ⏳ Pending | - | |
| Audit Gate | ⏳ Pending | - | |

## 文档导航

### PRD（认知层）
- [prd-v1-initial.md](prd-v1-initial.md)

### Spec（规范层）
- 待创建

### Plan（执行计划层）
- 待创建

### Test（测试层）
- 待创建

### Code（代码实现层）
- 待创建

### Review（AI 审计层）
- 待创建

## 参考

- [Vibe Workflow Paradigm](../../prds/vibe-workflow-paradigm.md)
- [文档组织标准](../../standards/DOC_ORGANIZATION.md)
