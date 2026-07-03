# Specification Quality Checklist: Governance Chain Baseline

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-07-03
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] 无实现细节泄漏（仅契约层面：三层合并、审计证据模型、角色分工、overlay 机制）
- [x] 聚焦行为契约与不变式
- [x] 面向后续变更者（描述 governance chain 现状）
- [x] 所有 mandatory section 已完成

## Requirement Completeness

- [x] 无 [NEEDS CLARIFICATION] 标记残留
- [x] 需求可测、无歧义（14 条 FR 对应现有材料/代码可复现）
- [x] 成功标准可测（6 条 SC 对应可回归验证）
- [x] 所有 acceptance scenario 已定义（6 story + edge cases）
- [x] Edge cases 已识别（三层边界、overlay 文件名匹配、intake 不越界、code-auditor 不越级、apply 的 L2 限制、材料清单、非 label-triggered）
- [x] scope 已明确界定（与 002/003/004 的边界）
- [x] 依赖与假设已识别

## Feature Readiness

- [x] 所有功能需求有明确验收依据
- [x] 行为场景覆盖主流程（三层合并 / intake 三级审查 / 4 层审计 / scan vs apply / overlay / 审计门）
- [x] feature 满足 SC 中定义的可测属性
- [x] 无实现细节泄漏

## Constitution Compliance

- [x] 原则 I：baseline 为后续 governance 演进提供契约参照
- [x] 原则 II：引用 [ADR-0005](../../../../docs/decisions/0005-prompt-policy-skill-audit-evidence-model.md) / [SOUL.md](../../../../SOUL.md) / [CLAUDE.md](../../../../CLAUDE.md) / [.claude/rules/*](../../../../.claude/rules/)，未复述权威内容
- [x] 原则 III：每条 FR/SC 关联可复现材料/代码现状
- [x] 原则 IV：未要求新增 Python 命令层；描述现有 governance 材料与合并机制
- [x] 原则 V：spec 产出在 `.specify/specs/005-governance-chain/`，随分支流转

## Notes

- 本 spec 为逆向规格化 baseline。PR #3291（dry-run 条件清理）、#3242 的行为已固化为现状契约。
- 4 层审计证据模型由 [ADR-0005](../../../../docs/decisions/0005-prompt-policy-skill-audit-evidence-model.md) 定义，本 spec 引用结论不重新论证。
- 三层策略合并的权威层级：`SOUL.md > CLAUDE.md > .claude/rules/* > supervisor/policies + .vibe overlay`，本 spec 描述机制不复述权威内容。
- 与 002/003/004 协作点：governance/supervisor 非 label-triggered（003 FR-010）、走同步执行（002 FR-008）、supervisor/apply 持 L2 worktree（004 FR-001）。
