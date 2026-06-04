---
document_type: decision
title: <决策标题>
adr_id: NNNN
status: proposed | accepted | superseded
date: YYYY-MM-DD
supersedes: null | ADR-NNNN
superseded_by: null | ADR-MMMM
related_docs:
  - <path/to/related/doc1.md>
  - <path/to/related/doc2.md>
issues:
  - <issue-number>
---

# <决策标题>

## Context

描述决策背景：
- 当前面临什么问题或挑战？
- 有哪些约束条件？
- 有哪些可选方案？

## Decision

陈述决策内容：
- 选择了哪个方案？
- 为什么选择这个方案？
- 关键权衡点是什么？

## Consequences

分析决策后果：
- 正面影响：解决了什么问题？带来了什么收益？
- 负面影响：引入了什么限制或成本？
- 风险：需要关注哪些潜在问题？

## How

**硬约束：本段只放链接，禁止复制实现细节。**

相关实现和操作流程见：

- [<实现文档>](<path/to/implementation.md>) — <简要说明>
- [<标准文档>](<path/to/standard.md>) — <简要说明>
- [<RFC issue>](https://github.com/<org>/<repo>/issues/<number>) — 原始问题讨论

---

<!-- ADR 模板说明 -->
<!--
1. 复制此模板创建新 ADR 文件，命名为 NNNN-kebab-title.md
2. 填写 frontmatter 和正文各段
3. 在 INDEX.md 中登记新 ADR（status: proposed）
4. ADR PR 合并后更新 INDEX.md（status: accepted）
5. 如需取代旧 ADR，新 ADR 填写 supersedes；旧 ADR 只允许更新 lifecycle metadata（status/superseded_by）并更新 INDEX

关键原则：
- ADR 记录"为什么"，不记录"怎么做"
- How 段只放链接，不复制实现细节
- ADR 一旦 accepted，决策正文不可重写；只能通过 supersede 机制被新 ADR 取代
- supersede 时允许更新旧 ADR 的 lifecycle metadata，以保持追溯链可读
-->
