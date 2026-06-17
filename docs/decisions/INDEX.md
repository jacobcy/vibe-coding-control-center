---
document_type: index
---

# Architecture Decision Records

本目录存放架构决策记录 (ADR)，记录"为什么"和"决策了什么"。

## 决策总表

| ID | 标题 | 状态 | 日期 | 取代 | 被取代 | 关联 Standard |
|----|------|------|------|------|--------|---------------|
| [ADR-0001](0001-adopt-adr-loop.md) | 采纳 RFC→ADR→Standards 闭环 | accepted | 2026-06-04 | - | - | docs/standards/doc-organization.md |
| [ADR-0002](0002-protocol-based-di.md) | Protocol-based Dependency Injection | accepted | 2026-06-04 | - | - | docs/standards/v3/architecture-convergence-standard.md |
| [ADR-0003](0003-runtime-loading-contract.md) | 运行时加载时机契约 — Kernel/Material/Job 三层与可插拔边界 | accepted | 2026-06-09 | - | - | docs/standards/v3/runtime-loading-contract.md（待写） |
| [ADR-0004](0004-domain-flow-event-boundary.md) | DomainEvent 与 FlowEvent 分层边界及投影关系 | accepted | 2026-06-12 | - | - | docs/standards/v3/event-driven-standard.md |
| [ADR-0005](0005-prompt-policy-skill-audit-evidence-model.md) | Prompt/Policy/Skill 审计证据模型 | proposed | 2026-06-17 | - | - | docs/standards/v3/database-schema-standard.md |
| ADR-XXXX | 3-Tier Layering 演进路径 | backlog | - | - | - | （待补写） |
| ADR-XXXX | Orchestra 编排机制 | backlog | - | - | - | （待补写） |

## 使用指南

- **发现入口**：本文件提供所有 ADR 的索引和状态追踪
- **模板文件**：[_template.md](_template.md) — 新建 ADR 时复制此模板
- **编号规则**：4 位顺序号（0001, 0002, ...），支持 supersede 链
- **状态流转**：`proposed` → `accepted` → `superseded`

## Supersede 追踪

当新决策取代旧决策时：
1. 在新 ADR 的 frontmatter 中填写 `supersedes: ADR-NNNN`
2. 在旧 ADR 的 frontmatter 中填写 `status: superseded` 和 `superseded_by: ADR-MMMM`
3. 在本 INDEX 中更新旧 ADR 状态为 `superseded`

ADR 的决策正文一旦 accepted 不得重写；supersede 只允许更新 lifecycle metadata 和 INDEX，以保持当前有效决策可追溯。

## 相关文档

- [ADR 模板](_template.md)
- [文档组织标准](../standards/doc-organization.md)
- [治理闭环](../governance/governance-roadmap-closed-loop.md)
