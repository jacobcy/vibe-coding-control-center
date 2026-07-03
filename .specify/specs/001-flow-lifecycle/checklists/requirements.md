# Specification Quality Checklist: Flow Lifecycle Baseline

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-07-03
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] 无实现细节泄漏（语言/框架/具体 SQL/类继承结构）— 仅契约层面（状态、事件、API 契约、不变式）
- [x] 聚焦行为契约与不变式（baseline 语境下"用户价值"= 系统行为保证）
- [x] 面向后续变更者（描述"系统现在如何行为"，作为回归基线）
- [x] 所有 mandatory section 已完成

## Requirement Completeness

- [x] 无 [NEEDS CLARIFICATION] 标记残留
- [x] 需求可测、无歧义（每条 FR 对应现有代码或命令可复现）
- [x] 成功标准可测（每条 SC 对应可回归测试）
- [x] 成功标准不绑定实现细节
- [x] 所有 acceptance scenario 已定义（6 个 story 各含 Given/When/Then）
- [x] Edge cases 已识别（遗留迁移、代码-文档差异、多 flow 保护、label 缺口、软删除隔离、loop 防护）
- [x] scope 已明确界定（与 002/003/004 spec 的边界）
- [x] 依赖与假设已识别（真源分层、写入权边界、与 standard 的偏差）

## Feature Readiness

- [x] 所有功能需求有明确验收依据（代码现状）
- [x] 行为场景覆盖主流程（完成、阻塞、依赖、恢复、重建、被动清理）
- [x] feature 满足 SC 中定义的可测属性
- [x] 无实现细节泄漏进 spec

## Constitution Compliance (baseline 特有维度)

- [x] 原则 I（Cognition First）：spec 先于代码变更，baseline 为后续演进提供契约参照
- [x] 原则 II（Single Source of Truth）：引用 [flow-lifecycle-standard.md](../../../../docs/standards/flow-lifecycle-standard.md) / [CLAUDE.md](../../../../CLAUDE.md) / [glossary.md](../../../../docs/standards/glossary.md)，未复述上游真源内容；代码-文档差异显式标注
- [x] 原则 III（Verification Before Claim）：每条 FR/SC 关联可复现的代码现状或测试
- [x] 原则 IV（Bridge）：未要求新增 Python 命令层；描述现有 `vibe3` 命令行为
- [x] 原则 V（Worktree-Isolated）：spec 产出在 `.specify/specs/001-flow-lifecycle/`，随 `dev/issue-3299` 分支流转

## Notes

- 本 spec 为 **逆向规格化 baseline**，描述代码现状行为契约，非新功能需求。其价值在于：后续对 flow-lifecycle 的任何变更（重构、bugfix、演进）均可对照本 spec 验证行为是否漂移。
- 已知 baseline 偏差（`failed` 终态、`AbandonFlowService` dead code、aborted/stale label 缺口）在本 spec 显式记录，修正属于后续 issue。
- 与 [flow-lifecycle-standard.md](../../../../docs/standards/flow-lifecycle-standard.md) 的关系：standard 是目标规范，本 spec 是现状契约；二者偏差通过文档/代码维护流程收敛，不在 spec 内单方面修改。
