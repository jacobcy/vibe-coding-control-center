---
document_type: decision
title: 采纳 RFC→ADR→Standards 闭环
adr_id: 0001
status: accepted
date: 2026-06-04
supersedes: null
superseded_by: null
related_docs:
  - docs/governance/governance-roadmap-closed-loop.md
  - docs/standards/doc-organization.md
  - docs/standards/v3/human-mirror-architecture-philosophy.md
issues:
  - 2015
---

# 采纳 RFC→ADR→Standards 闭环

## Context

现有 RFC/roadmap 闭环中决策易失，无跨任务架构决策耐久记录。"为什么"已零散存在于：
- RFC issue comments（易失，随 issue 关闭而沉没）
- PR descriptions（散落各处，难以检索）
- Standards 文档（只记录"怎么做"，不记录决策理由）

问题：
- 不同任务对同一架构问题重复讨论
- 新 contributor 难以理解历史决策背景
- Standards 无法追溯"为什么这样规定"

## Decision

采纳薄决策层 + 链接式 ADR 体系，三层按生命周期定位：

1. **RFC（问题/易失）**：提出问题、讨论方案、决策选型
2. **ADR（为什么/不可变）**：记录决策理由、权衡过程、关键结论
3. **Standards（怎么做/living）**：规定实现细节、操作流程、验收标准

核心原则：
- ADR 只写"为什么"和"决策了什么"，不写实现细节
- ADR 的 How 段只放链接，禁止复制 Standards 内容
- ADR 一旦 accepted 即不可修改，只能通过 supersede 机制被新 ADR 取代

## Consequences

正面影响：
- 架构级 RFC 决策不再蒸发，有据可查
- plan/task 决策时可快速检索历史决策
- 边界铁律（ADR 只写为什么，How 只放链接）防止重复记录
- 现有 philosophy 文档不搬家，保持稳定

负面影响：
- 增加一层文档结构，需要维护 INDEX
- RFC → ADR 结晶需要额外步骤

风险：
- ADR 约定可能被忽略（纯 policy，无 CI 门禁）
- 历史决策 backlog 指针可能过时

## How

**硬约束：本段只放链接，禁止复制实现细节。**

相关实现和操作流程见：

- [docs/standards/doc-organization.md](../standards/doc-organization.md) — 目录结构和命名规范
- [docs/governance/governance-roadmap-closed-loop.md](../governance/governance-roadmap-closed-loop.md) — RFC→ADR→Standards 闭环机制
- [skills/vibe-task/SKILL.md](../../skills/vibe-task/SKILL.md) — 任务执行中的 ADR 结晶流程
- [skills/vibe-roadmap/SKILL.md](../../skills/vibe-roadmap/SKILL.md) — RFC intake 中的 ADR 判据
- [supervisor/policies/plan.md](../../supervisor/policies/plan.md) — 规划前的 ADR 消费检查
- [RFC issue #2015](https://github.com/jacobcy/vibe-coding-control-center/issues/2015) — 原始问题讨论
