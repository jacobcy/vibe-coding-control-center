# Feature Specification: ADR Context Recall (ADR 按需召回)

**Feature Branch**: `011-adr-recall`
**Created**: 2026-07-03
**Status**: Draft
**Input**: User description: "为 ADR 按需召回（ADR Context Recall）写 spec。痛点：plan 时 agent 不读 ADR。经 7 轮 brainstorm grill 已确定瘦方案（零 Python，双层 enforcement）。"

---

## User Scenarios & Testing

### User Story 1 - Planner 按需召回相关 ADR 并产出可审计 artifact (Priority: P1)

作为 planner agent，在为一个 issue 起草 plan 时，我需要识别出与当前改动相关的 accepted ADR、只读这些 ADR 的正文，并在 plan 中留下"我评估了哪些 ADR、哪些适用、哪些豁免及理由"的可审计痕迹，而不是全量通读 `docs/decisions/INDEX.md` 凭直觉挑选。

**Why this priority**: 这是原痛点的直接解——"plan 时 agent 不读 ADR"。没有这条，reviewer 无 artifact 可审，整套 enforcement 不成立。它是核心闭环的入口。

**Independent Test (MVP)**: 给定一个改动 `src/vibe3/execution/flow_dispatch.py` 的 issue，运行召回程序后，plan 中出现 ADR-Consideration 节，列出至少评估了相关 accepted ADR（如运行时加载/事件边界类决策），并标注适用/豁免与理由。

**Acceptance Scenarios**:

1. **Given** 一个涉及 `src/vibe3/execution/` 改动的 plan, **When** planner 执行召回程序, **Then** plan 含 ADR-Consideration artifact，且 artifact 列出所有 scope 命中该路径的 accepted ADR。
2. **Given** INDEX.md 有多条 ADR, **When** planner 完成召回, **Then** planner 仅读取了相关 ADR 的正文（选择性），其余仅读 `decides` 摘要——召回成本不随 ADR 总数线性增长。
3. **Given** 某条 ADR 被评估后豁免, **When** artifact 生成, **Then** 豁免项附带理由（不允许空豁免）。
4. **Given** 召回返回零相关 ADR, **When** artifact 生成, **Then** artifact 记录"已评估全部 accepted ADR，均不适用"及逐条理由，而非默认放行。

### User Story 2 - Reviewer 审计 ADR 合规并阻断违规 (Priority: P1)

作为 reviewer（agent 或人类），在 review 阶段，我需要审计 plan 的 ADR-Consideration artifact 是否完整、豁免是否合理、腐烂标记是否已处理、plan 是否违反了某条 accepted ADR；若违反，通过现有 FailedGate / block-flow + roadmap·rfc 标签机制阻断，而不是仅记一笔建议。

**Why this priority**: enforcement 的"牙齿"在这里。没有有牙的 review-gate，US1 的 advisory 就是现状的重演——agent 可静默跳过。

**Independent Test (MVP)**: 给定一个 plan，其实现违反了某 accepted ADR（如混用了被 ADR 禁止的耦合方向），但 artifact 把该 ADR 标为"豁免"且无理由，review-gate 应阻断 flow 并打 roadmap·rfc 标签。

**Acceptance Scenarios**:

1. **Given** plan 的 artifact 漏评了一条 scope 命中的 accepted ADR, **When** reviewer 审计, **Then** flow 被阻断并打 roadmap·rfc 标签。
2. **Given** plan 实现违反了某 accepted ADR 但 artifact 将其豁免且无理由, **When** reviewer 审计, **Then** 阻断。
3. **Given** artifact 完整、豁免均有理由、无违反、腐烂标记已处理, **When** reviewer 审计, **Then** 通过。

### User Story 3 - ADR 作者维护 frontmatter 刻面质量 (Priority: P2)

作为 ADR 作者（人类或 agent），在新建/更新 ADR 时，我需要按模板填写 `decides`（决策对象+约束，一句话，<120 字）和 `scope`（path globs），并有写作示导与反例可参考，使 INDEX.md 的 `decides` 列可被召回程序扫描判断相关性。

**Why this priority**: 数据层是 US1/US2 的地基。`decides` 低质或 `scope` 缺失，召回第一步就判断不了相关性。但它是支撑性工作，不在核心闭环主路径上，故 P2。

**Independent Test (MVP)**: 新建一条 ADR 不填 `decides`，模板示导与召回自检应能发现并提示。

**Acceptance Scenarios**:

1. **Given** 作者新建 ADR, **When** 套用 `_template.md`, **Then** 模板含 `decides`/`scope` 字段及写作示导（含反例）。
2. **Given** ADR 的 `decides` 写成"我们选了事件驱动"（模糊、无约束）, **When** 召回执行 `decides` 质量自检, **Then** 标记为低质并在 artifact 反映。
3. **Given** ADR-0006 取代 ADR-0004, **When** 作者填 `scope`, **Then** 模板/示导提示需覆盖被取代者的 `scope`（继承），避免双重漏判。

### Edge Cases

- **scope rot（范围腐烂）**: 代码从 `src/vibe3/execution/` 重构到 `src/vibe3/orch/`，ADR 的 `scope` glob 失效。召回的 scope 健康自检应标记腐烂（路径不存在），artifact 反映，reviewer 决定是更新 ADR 还是豁免并说明。
- **supersede 漏继承**: ADR-0006 取代 0004 但未声明继承 0004 的 `scope`。INDEX 标 0004 为 superseded，0006 的 `scope` 又不覆盖相关文件 → 双重漏判。scope 健康自检应检测继承覆盖缺口。
- **decides 低质**: 模糊 `decides`（如"选了 X"而非"X 禁止 Y，因为 Z"）导致召回第一步误判相关性（漏召或过召）。由 `decides` 质量自检 + 模板示导缓解，artifact 显式标记低质项。
- **零匹配假阴性**: 召回返回无相关 ADR，可能是 scope rot / issue 未命名组件 / 分支陈旧导致。artifact 必须记录"评估了全部 accepted ADR，均不适用 + 逐条理由"，reviewer 审计零匹配主张是否成立，而非默认放行。
- **分支陈旧**: 当前分支早于某 accepted ADR 合入，召回看不到该 ADR。artifact 应注明召回基线的 ADR 快照（分支/commit），reviewer 判断是否需 rebase 后重审。
- **大规模（明确延期）**: ADR 数量超过阈值（如 15-20）后，纯 agent 判断 + INDEX.md `decides` 列通读不再可行，需引入检索引擎/评分/分层披露。本期不做，留 follow-up feature。

---

## Requirements

### Functional Requirements

**数据层（markdown only）**

- **FR-001**: ADR 模板（`_template.md`）MUST 新增 `decides`（决策对象+约束，一句话，<120 字）与 `scope`（path globs）字段，并附写作示导与反例。
- **FR-002**: 现有全部 accepted ADR MUST 回填 `decides` 与 `scope`。
- **FR-003**: `INDEX.md` MUST 提供 `decides` 摘要列，使 agent 可一次性扫描全部 ADR 的相关性（Tier 0）。

**召回程序（recall）**

- **FR-004**: 项目 MUST 提供一个召回入口（spec-kit extension 形态，**非** Python 命令），引导 agent 按有序 checklist 执行：读 `decides` 列判语义相关性 → 改动文件匹配 `scope` 判代码相关性 → `decides` 质量自检 → `scope` 健康自检 → 读命中 body → 产 artifact。
- **FR-005**: 召回 MUST 产出一个 "ADR-Consideration" artifact，含：评估的 ADR 集合、适用集合、豁免集合+理由、自检结果、腐烂标记、ADR 快照基线（分支/commit）。
- **FR-006**: 召回 MUST 内嵌 `decides` 质量自检（须含决策对象+约束，<120 字），低质项在 artifact 标记。
- **FR-007**: 召回 MUST 内嵌 `scope` 健康自检：`scope` glob 引用的路径是否存在、supersede 链的 `scope` 继承是否覆盖；缺口在 artifact 标记为腐烂。
- **FR-008**: 召回 MUST 支持以当前 issue + 改动文件（来自现有改动检查能力）为上下文，输出有界的相关 ADR 集合（非全量）。

**artifact**

- **FR-009**: 非平凡变更的 plan MUST 包含 "ADR Consideration" 节（即召回产出的 artifact），作为 plan 可审计性的必要组成。

**review-gate**

- **FR-010**: review 阶段 MUST 审计 plan 的 ADR-Consideration artifact：是否完整（未漏评 scope 命中的 accepted ADR）、豁免是否附理由、腐烂标记是否已处理、plan 是否违反被豁免/适用的 accepted ADR。
- **FR-011**: 审计发现违规时 MUST 通过现有 FailedGate / block-flow / roadmap·rfc 标签机制阻断（复用，不新建并行 enforcement）。

**policy 接线**

- **FR-012**: `supervisor/policies/plan.md`（§84 及相关）、`skills/vibe-task`、`skills/vibe-roadmap` 中"读 INDEX.md"类指令 MUST 改为"执行召回程序 + 产 ADR-Consideration artifact"。
- **FR-013**: `.specify/memory/constitution.md` MUST 增补一节，声明 principles（SOUL/CLAUDE/rules）↔ spec（per-feature）↔ ADR（cross-cutting 决策）的三层互补关系。

**边界（明确不做）**

- **FR-014**: 本期 MUST NOT 新增 `vibe3 adr` Python 命令层、评分算法、三层 progressive disclosure 检索引擎或 embeddings/RAG；这些延期至 ADR 数量过阈值（如 15-20）后另立 feature。

### Key Entities

- **ADR**: 已有实体（`adr_id`, `status`, `supersedes`/`superseded_by`, `issues`, `related_docs`）；本期扩展 `decides`（一句话决策摘要）、`scope`（path globs）。
- **ADR-Consideration Artifact**: 召回产出物。字段：`evaluated_adrs`、`applicable`、`dismissed`+`reason`、`decides_quality_flags`、`scope_rot_flags`、`adr_snapshot_baseline`（分支/commit）。
- **Recall Checklist**: 有序步骤（语义相关性 → 代码相关性 → `decides` 自检 → `scope` 自检 → 读 body → 产 artifact），由 extension 命令承载。
- **Review Gate Decision**: pass / block（附 roadmap·rfc 标签 + 阻断理由）。

---

## Success Criteria

### Measurable Outcomes

- **SC-001（选择性）**: planner 完成一次召回时，读取的 ADR 正文数量显著少于 ADR 总数（仅读命中项 body，其余仅读 `decides` 摘要）；召回成本不随 ADR 总数线性增长。
- **SC-002（artifact 覆盖）**: 每个非平凡变更的 plan 都包含完整的 ADR-Consideration artifact，作为 review 前置；无 artifact 的 plan 被阻断。
- **SC-003（阻断有效）**: 凡 plan 实现违反 accepted ADR 的，review-gate 在合入前阻断（block flow + 标签），无静默放行。
- **SC-004（腐烂可见）**: scope rot 或 supersede 继承缺口在一次召回周期内被标记到 artifact，而非长期沉默。
- **SC-005（复用不重建）**: 全部 enforcement 通过现有 audit/gate/label 机制达成，不引入并行的强制系统，且不新增运行时命令层代码。

---

## Assumptions

- ADR 当前数量小（≤15），纯 agent 判断 + INDEX.md `decides` 列扫描可行；检索引擎/评分延期（YAGNI，对齐 HARD RULES #15 最短路径优先、#16 Skill-First）。
- 现有 review-gate / FailedGate / block-flow / roadmap·rfc 标签机制可直接复用，无需改造其内核。
- 相关性判断采用确定性刻面（`decides` 语义 + `scope` 代码 glob）+ agent 判断，不使用 embeddings/RAG。
- 召回入口以 spec-kit extension（markdown 命令）形态交付，不新增 Python 命令层（HARD RULES #16 agent/skill-first）。
- `constitution.md` 的增补遵循其既有 semver 治理（MAJOR/MINOR/PATCH）。
- 本 feature 只覆盖 `docs/decisions/` 下的人类决策 ADR；与 `.specify/specs/` 的 spec、与 `.claude/rules/` 的原则，三者职责互补、不重叠（单一事实原则）。

---

## Design Decisions (Brainstorm Audit Trail)

以下决议来自 7 轮对抗性盘问（`/speckit-superspec-brainstorm grill me`），作为 plan 阶段的设计约束记录：

| # | 议题 | 决议 | 理由 |
|---|------|------|------|
| Q1 | gate vs advisory | plan 阶段 advisory + review 阶段 gate（双层），复用 blocked/failed flow audit | 纯 gate 误伤正常流程（非所有 issue 命中 ADR）；纯 advisory 无约束（现状）。事后审计 + 现有 FailedGate/标签最契合 |
| Q2 | 落点 | plan 建议层，review 门槛层 | 充分利用已有机制，最小新代码 |
| Q3 | 是否新增命令 | 不，做薄 spec-kit extension | 项目 agent/skill-first，动代码太早（HARD RULES #16） |
| Q4 | extension vs gate 边界 | extension=注入召回流程，gate=vibe3 review policy | 职责分离 |
| Q5 | 三者叠加 | 数据层（decides/scope）+ 程序（recall checklist）+ artifact（可审计产物） | 缺任一层都不闭环 |
| Q6 | decides 强制 | checklist 内嵌 `decides` 自检 | 无引擎时，质量靠自检 + 模板示导兜底 |
| Q7 | scope rot | checklist 内嵌 `scope` 健康自检（路径存在 + supersede 继承覆盖，标记腐烂） | scope 是 recall 相关性的代码锚点，必须可探测失效 |
