---
document_type: template
template_for: prd
description: Template for Product Requirements Documents (PRD) following Vibe Workflow Paradigm
author: Claude Sonnet 4.5
created: 2025-01-24
last_updated: 2025-01-24
related_docs:
  - docs/prds/vibe-workflow-paradigm.md
  - docs/README.md
  - docs/standards/doc-quality-standards.md
---

# PRD: {{TASK_TITLE}}

> 本文档定义 {{TASK_TITLE}} 的产品需求。

## 业务目标

**核心能力**：[描述要实现的核心能力]

**示例**：
- 实现 Plan Gate 能读取多种格式的计划文件
- 提供统一的文档组织标准

## 绝对边界（不做什么）

**明确拒绝项**：[列出不做的事情，防止 AI 过度设计]

**示例**：
- 不负责创建计划，不负责框架选择
- 不实现自动化代码生成

## 核心数据流

**输入 → 处理 → 输出**：

```
[输入] → [处理逻辑] → [输出]
```

**示例**：
```
framework 字段 → 路径映射 → 文件内容
```

## 成功判据

**如何判断成功**：[定义验收标准]

**示例**：
- 能正确读取 OpenSpec 和 Superpower 格式
- 所有文档符合标准结构

---

## Scope Gate 验证标准

- [ ] 业务目标明确
- [ ] 绝对边界清晰
- [ ] 核心数据流完整
- [ ] 成功判据可验证
