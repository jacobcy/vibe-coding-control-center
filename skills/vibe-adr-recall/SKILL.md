---
name: vibe-adr-recall
description: Use when creating or reviewing a non-trivial spec-kit implementation plan to recall applicable accepted ADRs from docs/decisions/ and record a structured ADR Consideration artifact in the plan. Agent-only and low-code - scans ADR frontmatter (decides/scope) and reads candidate bodies only; no runtime command, database, scoring, embeddings, or RAG. Triggers at plan time (planned paths + issue/spec semantics) and at review time (actual merge-base diff reconciliation).
---

# Vibe ADR Recall

> 把 ADR 考量变成 plan / review 阶段的结构化 agent 责任：plan 记录意图，review 对照实际 diff。

## Overview

`vibe-adr-recall` 让 agent 在产出或审查 spec-kit plan 时，**显式**确认当前 accepted ADR 是否约束本次变更，并把证据写进 plan 的 `ADR Consideration` 段。

这是**纯 agent 推理 + Markdown/YAML** 能力（spec FR-014）。不引入 Python 命令、数据库、评分服务、embeddings 或 RAG。

## When to Use

- 用 `/speckit-plan` 产出非平凡 implementation plan 时（plan 阶段）。
- review 阶段对照实际 merge-base diff 与当前 accepted ADR snapshot（review reconciliation）。
- 计划触及跨切面决策、`src/vibe3/` 架构层、共享状态、或 ADR 明确约束的路径。

## When NOT to Use

- 纯文档拼写修正、与本仓任何 ADR 决策对象/scope 无关的琐碎改动 → 直接记 zero-candidate，无需读 ADR body。
- 问答、概念治理、roadmap 规划本身（不产出 implementation plan）。

## Low-code boundary（硬约束）

- **禁止**调用或规划 `vibe3 adr`、Python 评分/检索服务、数据库、embeddings、RAG。
- 元数据扫描是对 accepted ADR 的**线性**遍历；全 body 读取只针对候选。
- 阈值（spec FR-015）：仅当 accepted ADR > 20，**或** ≥10 份已审查 plan 存在测得的 false-positive/false-negative 证据证明本 procedure 不可靠时，才可经后续 RFC 提议 code-assisted retrieval。在此之前任何“上代码”的提议都偏离本 skill。

## Inputs

| 字段 | Plan 阶段 | Review 阶段 |
|---|---|---|
| baseline | 当前 branch + commit | 被审查 head + merge base |
| 语义输入 | issue + spec + plan summary | plan + PR purpose |
| paths | **planned** 仓库相对路径（来自 issue/spec/plan，不假装实现 diff 已存在） | **actual** merge-base diff 路径 |
| ADR snapshot | planning baseline 下的 accepted 文件 | review baseline 下的 accepted 文件 |

**Plan 阶段禁止**用 `vibe3 inspect base` 作为“未来文件”的证据（spec FR-006）：实现前它只能显示已有分支差异，不能证明将要创建的文件。

## Procedure — Plan stage

1. 记录 baseline（branch + commit）、issue/spec 语义、planned 仓库相对路径。
2. 发现 `docs/decisions/*.md`，读 frontmatter。
3. **accepted snapshot** 仅由 `status: accepted` 的文件构成；忽略 `_template.md` 与 INDEX 中无对应文件的 placeholder 行。
4. 对每个 accepted ADR，检视 `decides` 与 `scope`。
5. **候选判据（spec FR-007）**：semantic 相关 **OR** scope 相关即纳入候选。两者皆无则不纳入。metadata 缺失/薄弱**保守地**纳入候选并记 flag（不静默忽略）。
6. **只读候选 ADR 的 body**；非候选不读 body。
7. 每个候选必须 resolve 为 applicable 或 dismissed，dismissed 要给**具体**理由（读了 body 之后得出）。**只**对进入候选集的 ADR 写 dismissal reason（spec FR-009）。
8. 记录 compliance、open conflicts、以及任何 ADR change proposal（carry/replace/retire）。
9. 把 artifact 写进生成的 plan，先于 spec-kit `review-plan` gate。

## Procedure — Review stage

1. 用既有 review 证据工具取得 actual merge-base diff（`git diff <merge-base>...HEAD`）。
2. 在 review baseline 刷新 accepted ADR snapshot。
3. 用 **actual paths** 重跑 semantic/scope 候选选择。
4. 比较 review 候选/约束与 plan artifact。
5. **追加** reconciliation 证据（不改写 plan 记录）。
6. 对未解决的 accepted-ADR 违反、缺失 artifact 证据、或站不住脚的 dismissal，产出**正常** review finding + blocking verdict。
7. **不**激活 FailedGate、**不**打 label、**不**直接改 flow state（spec FR-012）。reviewer 的 verdict/state 与既有 no-op gate 负责执行；本 skill 只产出 finding。

## Candidate relevance rules

- **semantic**：issue/spec/plan 语义触及 ADR 的 `decides` 决策对象。
- **scope**：planned/actual 路径命中 ADR `scope` 的仓库相对 path/glob。
- 任一命中即候选。取**交集**会漏掉新文件、改名模块、跨切面策略变更与 stale scope（research Decision 4）。
- 模糊性留给“读候选 body 之后”再 resolve。

## Metadata flags

对 accepted ADR 的 metadata 健康度保守标注：

- `decides` 缺失或不含 must / must not / only 等绑定措辞。
- `scope` 缺失、含仓库外路径、或全为 `**` 通配（无法做 relevance 判定）。
- lifecycle/index 不一致（INDEX 标 accepted 但无文件，或反之）。

flag 不等于 dismissal；flag 的 ADR 仍作为候选并读 body。

## Supersede disposition（spec FR-013）

replacement ADR 必须对每个受影响 predecessor scope 标注 `carry | replace | retire` + reason。successor **无需**是 predecessor scope 的严格超集；narrowing/retirement 显式声明即合法。提议 supersede 走 RFC/ADR PR，不在本 skill 内自动落地。

## Artifact schema

plan 内嵌的 `ADR Consideration` 段，normative schema 见 `.specify/specs/011-adr-recall/contracts/artifact.md`。核心字段：`baseline / accepted_snapshot / paths / candidates / applicable / dismissed_candidates / metadata_flags / adr_change_proposals / open_conflicts / review_reconciliation`。

不变量（data-model.md）：

- `applicable` 与 `dismissed_candidates` 是 `candidates` 的子集。
- 每个候选要么 resolve，要么显式留作 open conflict。
- zero-candidate 结果有 scan 证据与 metadata flags，但**不**伪造逐条 exhaustive dismissal。
- review reconciliation 保留 plan 记录并**追加**实际 diff 证据。

## Examples

四种典型场景的可填充 artifact 见 `examples/`：

- `semantic-only.md` — 新文件路径不命中 scope，但 issue 语义选中 ADR。
- `scope-only.md` — review 实际 diff 命中 plan 时遗漏的 accepted ADR scope。
- `zero-candidate.md` — 琐碎文档修正，记录 scan 信号 + zero candidate，无 exhaustive dismissal。
- `metadata-flag.md` — accepted ADR 的 decides/scope 偏弱，保守纳入 + flag。

## References

- Spec：[`.specify/specs/011-adr-recall/spec.md`](../../.specify/specs/011-adr-recall/spec.md)
- Contracts：`contracts/{recall-checklist.md, artifact.md, adr-frontmatter.md}`
- Data model：[`data-model.md`](../../.specify/specs/011-adr-recall/data-model.md)
- ADR 真源：[`docs/decisions/`](../../docs/decisions/)（frontmatter 为 metadata 真源，INDEX 仅 discovery）
