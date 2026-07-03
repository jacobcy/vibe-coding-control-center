# Implementation Plan: ADR Context Recall (ADR 按需召回)

**Branch**: `011-adr-recall` | **Date**: 2026-07-03 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `.specify/specs/011-adr-recall/spec.md`

## Summary

一个**瘦方案、零 Python、双层 enforcement** 的 ADR 按需召回机制：

- **plan 阶段（advisory）**：planner 运行召回 skill，按 `decides` 语义相关性 + `scope` 代码 glob 相关性筛选 accepted ADR，只读命中项正文，产出可审计的 "ADR-Consideration" artifact。
- **review 阶段（gate）**：reviewer 审计该 artifact（完整性、豁免理由、腐烂标记、是否违反 accepted ADR），违反则给 BLOCK verdict，复用现有 FailedGate / block-flow + `roadmap/rfc` 标签机制产生约束力。

全部 enforcement 复用现有 audit/gate/label 机制（HARD RULES #15 最短路径优先），不新增 Python 命令层（HARD RULES #16 Skill-First）。技术载体为 markdown 数据层 + skill 程序 + policy 文本。

## Technical Context

**Language/Version**: Markdown + YAML frontmatter（数据层、artifact、policy）；skill markdown（召回程序）。**无 Python**（FR-014 边界）。
**Primary Dependencies**: spec-kit skill 机制（`.claude/skills/`）；**复用**（不新增）`vibe3 inspect base`（改动文件）、`vibe3 handoff`（artifact 落盘）、FailedGate（`src/vibe3/orchestra/failed_gate.py`）、`roadmap/rfc` 标签（`skills/vibe-roadmap`）。
**Storage**: markdown 文件——`docs/decisions/`、`.specify/memory/`、`supervisor/policies/`、`skills/`、`.claude/skills/`。
**Testing**: 无 pytest（零 Python 特性，by design）。验证改为可复现的**场景化验收**（见 [quickstart.md](./quickstart.md)）：在真实 issue 上跑召回 + 植入违规被 review 阻断。
**Target Platform**: Agent 工具链（Claude Code / spec-kit / supervisor 角色注入）。
**Project Type**: tooling / policy（markdown 扩展 + 策略文本）。
**Performance Goals**: N/A（ADR 数 ≤15，纯 agent 判断；过阈值后另立 feature，见 FR-014）。
**Constraints**:
- HARD RULES #15（最短路径优先——复用 FailedGate/标签/block-flow）
- HARD RULES #16（Skill-First——禁止新增 `vibe3 adr` Python 命令）
- HARD RULES #11（禁止框线字符——仅 ASCII `= - | +`）
- HARD RULES #8（worktree 隔离——改动落当前 `dev/issue-3299` worktree）
- ADR `How` 段已有"只放链接，禁止复制实现细节"硬约束——`scope` 字段是新增的代码锚点，不复述 `How`

## Constitution Check

*GATE: Must pass before proceeding. Re-check after design phase.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Cognition First, Spec Before Code | PASS | spec.md 已就绪（[spec.md](./spec.md)），本 plan 派生自 spec，不反向发明需求。 |
| II. Single Source of Truth (Reference, Don't Reimplement) | PASS | `decides`/`scope` 是 ADR-local 新字段，不复述上游；constitution 增补节只声明 spec↔ADR↔principle 三层**关系**（新内容），不复制 SOUL/CLAUDE/rules 内容。 |
| III. Verification Before Claim | NEEDS ATTENTION → 已解决 | 零 Python 意味着无 pytest；验证载体改为 artifact（可审计产物）+ review gate + quickstart 场景化验收（[quickstart.md](./quickstart.md)）。每个 task 仍须带可复现证据（HARD RULES #3），只是证据形态是"召回输出 + 植入违规被阻断的 review 记录"。 |
| IV. Bridge, Don't Reimplement (Skill-First) | PASS（最强） | 显式零 Python（FR-014），recall 以 skill 形态承载，enforcement 全部复用 FailedGate/BLOCK/`roadmap/rfc`。直接对齐 #15/#16。 |
| V. Worktree-Isolated Specs | PASS | spec/plan/tasks 在 `.specify/specs/011-adr-recall/`；对 `docs/decisions/`、`supervisor/policies/`、`skills/` 的改动均落当前 `dev/issue-3299` worktree 分支。 |

## Project Structure

### Documentation (this feature)

```text
.specify/specs/011-adr-recall/
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # Phase 0 设计决策
├── data-model.md        # Phase 1 实体（ADR frontmatter 扩展 + Artifact）
├── contracts/
│   ├── adr-frontmatter.md   # decides/scope 字段 schema
│   ├── artifact.md          # ADR-Consideration artifact schema
│   └── recall-checklist.md  # 召回程序行为契约
├── quickstart.md        # 场景化验收指南
└── tasks.md             # (/speckit-superspec-tasks 产出)
```

### Source Code (repository root)

本 feature **不新增任何 `src/vibe3/` Python 代码**。所有改动点为 markdown / policy 文本：

```text
docs/decisions/
├── _template.md                         # [数据层] 新增 decides/scope 字段 + 写作示导
├── INDEX.md                             # [数据层] 新增 decides 摘要列
├── 0001-adopt-adr-loop.md               # [数据层] 回填 decides/scope
├── 0002-protocol-based-di.md            # [数据层] 回填
├── 0003-runtime-loading-contract.md     # [数据层] 回填
├── 0004-domain-flow-event-boundary.md   # [数据层] 回填
└── 0005-prompt-policy-skill-audit-evidence-model.md  # [数据层] 回填

.claude/skills/
└── adr-recall/                          # [召回程序] NEW skill（形态决议见 research.md §1）
    └── SKILL.md                         #   承载 recall checklist + 自检逻辑

supervisor/policies/
├── plan.md                              # [接线] §84 改为"跑召回 + 产 artifact"
└── review.md                            # [门槛] 新增"ADR 合规审计"节 + BLOCK 规则

skills/
├── vibe-task/SKILL.md                   # [接线] line 125 改为"跑召回"
├── vibe-roadmap/SKILL.md                # [接线] line 444 改为"跑召回"
└── vibe-review-code/SKILL.md            # [门槛] review flow 增 artifact 审计步

.specify/memory/
└── constitution.md                      # [治理] 增补 spec↔ADR↔principle 三层关系节（MINOR bump）
```

**Structure Decision**:

- **recall 以独立 skill 承载**（`.claude/skills/adr-recall/`），而非 `.specify/extensions/<ext>/extension.yml` 钩子。理由：recall 由 plan policy **显式调用**（非生命周期钩子），skill 形态最薄、零扩展注册开销，对齐 HARD RULES #16。详细对比见 [research.md §1](./research.md)。
- **artifact 不新建目录**：直接作为 plan.md 的 "ADR Consideration" 节内嵌，随 plan 流转，避免新增落盘路径。
- **数据层 / 程序 / 门槛三流解耦**：数据层（decides/scope）是地基，程序（recall）消费它，门槛（review）审计产物——三者可独立审阅与回滚。

## Execution Strategy

### TDD Requirements

本特性零 Python，传统 Red-Green-Refactor 不直接适用。**TDD 适配为"场景化验收先行"**：先写 quickstart 验收场景（ failing：召回未产 artifact / 植入违规未被阻断），再实现使其通过。标记 [TDD-Scenario]：

- [TDD-Scenario] **recall 自检逻辑**（decides 质量 + scope 健康判定）：判定规则是逻辑，须有"低质 decides / 腐烂 scope 被正确标记"的样例（写入 skill 的 examples/）。
- [TDD-Scenario] **review gate 阻断**：植入一个违反 accepted ADR 的 plan，验证 review 给出 BLOCK + `roadmap/rfc`。

### Parallel Execution Opportunities

三条独立流（共享文件少），可并行派发子 agent：

- [SUBAGENT-A] **数据层**：`_template.md` + `INDEX.md` + 5 个 ADR 回填（自包含，仅动 `docs/decisions/`）。
- [SUBAGENT-B] **召回 skill**：`.claude/skills/adr-recall/SKILL.md` + 自检样例（依赖数据层字段定义，但可先按契约 [contracts/adr-frontmatter.md](./contracts/adr-frontmatter.md) 并行起草）。
- [SUBAGENT-C] **门槛 + 接线**：`review.md` + `vibe-review-code` + `plan.md §84` + `vibe-task:125` + `vibe-roadmap:444`（policy 文本，互不冲突）。

`constitution.md` 增补节由主 agent 收尾统一写（治理文本，不宜并行）。

注：均为 markdown 小改动，并行收益有限；若不并行，按 A→B→C 顺序串行亦可。

### Human Checkpoints

1. **数据层完成后**——人工核验 5 个 ADR 的 `decides`（决策对象+约束、<120 字）与 `scope`（path glob 覆盖真实代码）质量。
2. **召回 skill 完成后**——在一个真实 issue 上 dry-run 召回，确认 artifact 字段完整、选择性正确（不全量读 body）。
3. **门槛接线完成后**——植入违规 plan，确认 review 给 BLOCK + `roadmap/rfc`。
4. **合入前**——对照 spec.md 全部 FR 逐项复核。

### Review Gates

- [REVIEW] **recall skill + 自检逻辑**（编码 enforcement 判定，须 review 后再接入 plan policy）。
- [REVIEW] **artifact schema**（[contracts/artifact.md](./contracts/artifact.md)）——下游 review 审计依据，定稿前 review。
- [REVIEW] **gate 文本**（`review.md` 新增节 + BLOCK 规则）——enforcement 的"牙齿"，须 review 用词与现有 PASS/MAJOR/BLOCK 契约一致。

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

无 VIOLATION。Constitution Check 全 PASS（III 已解决）。本特性是**做减法**（复用、零 Python），不引入复杂度负债。

- 唯一"NEEDS ATTENTION"（原则 III）已通过 quickstart 场景化验收机制解决，不构成违规。
- 显式非目标（FR-014：Python 引擎/评分/embeddings）已边界化，避免过度工程。
