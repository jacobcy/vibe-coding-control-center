---
document_type: decision
title: Spec Artifact 与 Handoff 统一契约
adr_id: 0006
status: accepted
decides: "正式 spec 必须是 `.specify/specs/<NNN-slug>/spec.md` 下的仓库 artifact；spec/plan/report/audit 只通过统一 Handoff ref 契约发布，外部 workflow 只能经 project-owned extension adapter 接入，不得把 issue identity 复用为 spec_ref。"
scope:
  - .specify/specs/**
  - .specify/extensions/**
  - src/vibe3/services/handoff/**
  - src/vibe3/services/shared/spec_ref.py
  - src/vibe3/services/flow/consistency.py
  - src/vibe3/commands/handoff_*.py
  - src/vibe3/commands/flow_manage.py
  - supervisor/policies/plan.md
  - supervisor/policies/run.md
  - supervisor/policies/review.md
date: 2026-07-04
supersedes: null
superseded_by: null
related_docs:
  - .specify/specs/012-spec-handoff-bridge/spec.md
  - .specify/specs/001-flow-lifecycle/spec.md
  - .specify/specs/003-role-protocol/spec.md
  - .specify/specs/006-handoff-protocol/spec.md
  - docs/standards/v3/handoff-store-standard.md
issues:
  - 3310
---

# Spec Artifact 与 Handoff 统一契约

## Context

Vibe3 已经用 flow refs 表达阶段 artifact，并通过 `@plan`、`@report`、`@audit` 和 `@spec` 提供稳定读取别名，但 spec 的写入与验证没有进入同一套 Handoff contract：

- plan/report/audit 由 `HandoffService` 记录，spec 由 `flow update --spec` 或 `FlowService.bind_spec()` 写入；
- `spec_ref` 同时承载文件和 GitHub issue identity，而 task issue 已有独立字段；
- ref 写入、no-op 检查、读取和 consistency recovery 对“有效”的定义不同；
- spec-kit/superspec 能生成结构化 artifact，却没有项目自有 adapter 将产物发布到 flow；
- 自动化 role material 可以看到 ref，但没有统一的“存在则必须消费”约束。

这不是人机 workflow 与自动化 workflow 的合并问题。`dev/*` 人机协作可以选择任意方法，`task/*` 自动化仍由 label 驱动 plan/run/review。需要统一的是两种现场都能使用的 artifact 交换契约。

## Decision

采用 flow-scoped Handoff artifact contract 作为 spec/plan/report/audit 的统一交换边界：

1. 正式 spec 使用 repository-native `.specify/specs/<NNN-slug>/spec.md`；issue identity 不再兼任 `spec_ref`。
2. `spec -> spec_ref` 与现有 plan/run/review ref 同属 canonical Handoff artifact mapping。
3. 所有 authoritative ref 在写入前验证存在性、普通文件类型、worktree containment 与 artifact-specific canonical path，并以 repository-relative 形式保存。
4. 已登记 artifact 后来丢失属于可恢复的 artifact blocker：要求重新生成或重新绑定，不自动销毁 flow scene。rebuild 只处理 worktree/flow 物理现场损坏。
5. 自动化 role material 不假设 artifact 由哪种 workflow 生成；ref 存在时必须读取，ref 不存在时按该 role 的既有最小输入继续。
6. spec-kit、superspec、Superpowers 或其他外部 workflow 通过 project-owned extension/adapter 调用公开 Handoff capability；不修改外部源、不直接写共享数据库、不重新定义 label lifecycle。
7. accepted ADR 与当前 spec/issue/repository truth 是约束来源；claude-memory 等长期记忆只提供可回指的历史证据，不能覆盖当前真源。

## Consequences

正面影响：

- spec 与其他阶段 artifact 获得对称的写入、读取、验证和恢复语义；
- 自动化 planner 可以稳定消费已有 spec、ADR 与相关历史，而不绑定某个具体人机 workflow；
- spec-kit extension hooks 可以复用现有 Handoff capability，不需要 fork 外部项目；
- issue identity 与 spec artifact identity 不再混合。

负面影响：

- 现有 `spec_ref=#issue` 数据需要兼容迁移或清理策略；
- `flow update --spec` 需要降级为兼容入口，调用面和测试需要同步；
- 现有 missing-ref recovery 的 rebuild 分类必须调整；
- 直接运行不会触发 spec-kit core hooks 的外部 skill，需要额外的 repository exit contract。

风险：

- extension hook 与 role exit contract 若重复发布，必须保持幂等；
- artifact 路径过度收紧可能影响历史非 spec-kit 文档，需要显式迁移而非静默接受；
- memory retrieval 不可用时必须暴露证据限制，不能假装已完成历史召回。

## How

**硬约束：本段只放链接，禁止复制实现细节。**

相关实现和操作流程见：

- [Spec 012](../../.specify/specs/012-spec-handoff-bridge/spec.md) — 功能需求、失败语义和验收标准
- [Spec 001](../../.specify/specs/001-flow-lifecycle/spec.md) — flow consistency 与 recovery baseline
- [Spec 003](../../.specify/specs/003-role-protocol/spec.md) — role context enrichment 与 output contract baseline
- [Spec 006](../../.specify/specs/006-handoff-protocol/spec.md) — Handoff ref 与 artifact baseline
- [Handoff Store Standard](../standards/v3/handoff-store-standard.md) — 共享状态与 artifact 存储标准
- [Follow-up issue #3310](https://github.com/jacobcy/vibe-coding-control-center/issues/3310) — 实施范围和验收清单
