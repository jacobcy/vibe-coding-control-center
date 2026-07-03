# Quickstart: ADR Context Recall 验收指南

**Feature**: 011-adr-recall | **Spec**: [spec.md](./spec.md)

本特性零 Python（FR-014），无 pytest。验收通过**可复现场景**进行：在真实 issue 上跑召回、植入违规验证 review 阻断、触发 scope rot 验证可见性。每个场景给出前置条件、命令、预期结果。

---

## 前置条件

1. 数据层已就绪：
   - `docs/decisions/_template.md` 含 `decides`/`scope` 字段 + 示导
   - `docs/decisions/INDEX.md` 含 `decides` 摘要列
   - `docs/decisions/000{1..5}-*.md` 已回填 `decides`/`scope`
2. 召回 skill 已就绪：`.claude/skills/adr-recall/SKILL.md`
3. 接线已就绪：`supervisor/policies/plan.md §84`、`vibe-task:125`、`vibe-roadmap:444` 指向召回 skill
4. 门槛已就绪：`supervisor/policies/review.md` 含 "ADR 合规审计" 节

---

## 场景 1 — Happy Path：召回产出完整 artifact（验 US1 / SC-001 / SC-002）

**目的**: 验证召回按需读 ADR、产出完整 artifact、选择性强。

**步骤**:
1. 取一个触及 `src/vibe3/execution/` 或 `src/vibe3/domain/handlers/` 的真实 issue（应命中 ADR-0004 的 `scope`）。
2. 在该 issue 的 plan 阶段，planner 执行 `adr-recall` skill（由 plan.md §84 触发）。
3. 检查 plan.md 的 `## ADR Consideration` 节。

**预期结果**:
- `Baseline` 含当前 branch + commit SHA
- `Evaluated ADRs` 列出全部 accepted ADR（0001-0004 至少，0005 视 status）
- `Applicable` 含 ADR-0004（scope 命中），附约束要点 + plan 遵守评估
- `Dismissed` 含不相关 ADR，每条附理由
- planner **只读了** applicable ADR 的 body，其余仅读 `decides`（选择性，SC-001）

**通过判据**: artifact 字段完整（对照 [contracts/artifact.md](./contracts/artifact.md) 约束表），且 planner 未全量读 body。

---

## 场景 2 — Gate 阻断：植入违反 accepted ADR 的 plan（验 US2 / SC-003）

**目的**: 验证 review gate 对 ADR 违规给 BLOCK，复用 FailedGate + `roadmap/rfc`。

**步骤**:
1. 构造一个 plan：其实现让 DomainEvent handler 重新承担 flow 状态机判断（违反 ADR-0004 的 `decides`）。
2. plan 的 `ADR Consideration` 节把 ADR-0004 标为 `Dismissed`，**reason 留空**（或编造理由）。
3. 运行 review（`vibe3 review` 或 `vibe-review-code` skill），读 `supervisor/policies/review.md` 的 ADR 合规审计节。

**预期结果**:
- reviewer 识别 artifact 不完整（空豁免 / 漏评 scope 命中）
- verdict = **BLOCK**
- BLOCK 喂入 FailedGate，flow 阻断
- reviewer 在 comment 建议 打 `roadmap/rfc`（需人类拍板是否 supersede ADR-0004）

**通过判据**: verdict 为 BLOCK，flow 被阻断（非静默放行），`roadmap/rfc` 经建议触发（SC-003）。

---

## 场景 3 — Scope Rot 可见（验 US3 / SC-004）

**目的**: 验证 `scope` 健康自检把腐烂标记到 artifact。

**步骤**:
1. 临时把 ADR-0004 的 `scope` 改为指向一个**不存在**的路径（模拟重构后 glob 失效），如 `src/vibe3/old_runtime/**`。
2. 在任一触及事件代码的 issue 上跑召回。

**预期结果**:
- S4 自检标记 `scope_rot_flags: [{ADR-0004, missing_path, "src/vibe3/old_runtime/** 不存在"}]`
- artifact 的 `Self-Check Flags → scope rot` 反映该标记
- reviewer 据此要求先修 ADR-0004 的 `scope` 再放行（或附豁免理由）

**通过判据**: 腐烂在一次召回周期内出现在 artifact（SC-004），非长期沉默。事后还原 ADR-0004 的 `scope`。

---

## 场景 4 — 零匹配审计（验 Edge Case #4）

**目的**: 验证零匹配不被默认放行。

**步骤**:
1. 取一个纯文档/CI 配置类 issue（理论上不命中任何 ADR scope）。
2. 跑召回。

**预期结果**:
- `Applicable` 为空
- `Evaluated ADRs` 仍列全部 accepted ADR
- `Dismissed` 含全部 accepted ADR，每条附"为何 scope/语义不匹配"理由
- reviewer 审计零匹配主张成立 → PASS（或判定为平凡变更走豁免）

**通过判据**: 零匹配时 artifact 仍完整，reviewer 可验证"零相关"主张。

---

## 场景 5 — Supersede 继承缺口（验 Edge Case #2）

**目的**: 验证 supersede 链 scope 继承检测。

**前置**: 需一条 supersede 关系。若当前无（0001-0005 均无 supersede），可临时构造测试 ADR：ADR-9999 `supersedes ADR-0004`，但 `scope` 故意不覆盖 0004 的某条路径。

**步骤**: 跑召回。

**预期结果**:
- S4 自检标记 `scope_rot_flags: [{ADR-9999, supersede_gap, "未覆盖 ADR-0004 的 src/vibe3/runtime/**"}]`
- artifact 反映；reviewer 要求补全 ADR-9999 scope

**通过判据**: 继承缺口被检测并标记。事后删除测试 ADR。

---

## 总验收判据

- 场景 1-4 全部通过 → 本特性核心闭环（召回 + 门槛 + 腐烂 + 零匹配）可用。
- 场景 5（supersede）依赖测试数据，可在首个真实 supersede 发生时回归。
- 每个场景的运行记录（artifact 截图 / review verdict / flag 输出）作为 task 完成证据（HARD RULES #3），存入 issue comment 或 handoff。

---

## 非目标（不在本 quickstart 验收）

- Python 引擎 / 评分算法 / embeddings 检索（FR-014，延期）
- ADR 数量过阈值（>15-20）后的分层披露（延期）
- 自动 supersede scope 复制（人工修，见 [research.md §7](./research.md)）
