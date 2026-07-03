---
description: "Task breakdown for ADR Context Recall (zero-Python, dual-layer enforcement)"
---

# Tasks: ADR Context Recall (ADR 按需召回)

**Input**: Design documents from `.specify/specs/011-adr-recall/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), contracts/ (locked schema)
**Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Quickstart**: [quickstart.md](./quickstart.md)

## 本特性全局约束（先读）

- **零 Python**（FR-014）：本期不新增任何 `src/vibe3/` 代码、不新增 `vibe3 adr` 命令、无 pytest。全部交付物为 markdown / policy 文本 / skill。
- **TDD 适配为 `[TDD-Scenario]`**（见 plan.md Execution Strategy）：传统 Red-Green-Refactor 不适用；改为"场景化验收先行"——先写 quickstart 场景或自检黄金样例（failing：召回未产 artifact / 植入违规未被阻断 / 低质 decides 未被标记），再实现使其通过。
- **证据形态**（HARD RULES #3）：每个任务的证据是"召回 artifact 输出 / review verdict 记录 / 自检 flag 输出"，存入 issue comment 或 handoff，非测试日志。
- **ASCII only**（HARD RULES #11）：所有产出物仅用 `= - | +`，禁框线字符。

## Task Format

```
[ID] [markers] [Story] Description (FR/AC 追溯)
```

**Markers**:
- **[P]**: Can run in parallel (different files, no dependencies)
- **[TDD-Scenario]**: 场景化验收先行（本特性对 TDD 的适配，见上）
- **[REVIEW]**: Requires human review before proceeding
- **[SUBAGENT]**: Can be delegated to a subagent (对应 plan.md 三并行流 A/B/C)

**Story labels**: `[US1]`/`[US2]`/`[US3]` map to spec.md user stories (US1/US2 = P1, US3 = P2).

## Path Conventions

本特性改动点全部在仓库根的 markdown/policy/skill，无 `src/`：

- 数据层：`docs/decisions/`（`_template.md`、`INDEX.md`、`0001`-`0005`）
- 召回程序：`.claude/skills/adr-recall/`（NEW skill）
- 门槛/接线：`supervisor/policies/`、`skills/`
- 治理：`.specify/memory/constitution.md`

精确文件路径与行号在每个任务中标明。

---

## Phase 1: Setup (Lock Contracts)

**Purpose**: 确认 plan 阶段产出的三份契约已定稿，作为下游全部实现的不可变依据。

- [ ] T001 [REVIEW] 锁定契约 schema 定稿：审阅 `.specify/specs/011-adr-recall/contracts/adr-frontmatter.md`（`decides`/`scope` schema + 质量判据）、`contracts/artifact.md`（ADR-Consideration artifact schema + 字段约束表 + 零匹配规范 + 平凡变更豁免）、`contracts/recall-checklist.md`（S1-S6 状态机 + 5 不变量）。确认无占位符/TODO，schema 即为实现依据。（对应 plan.md [REVIEW] gate: artifact schema）

**Execution notes**: 契约在 plan 阶段已写就，本任务只做 review 锁定。下游 T002-T016 不得反向改契约；若实现暴露契约缺陷，回到本任务修订并重新 review。

**Checkpoint**: 契约锁定。获人工确认后再进入数据层。

---

## Phase 2: Foundational — 数据层（阻塞全部用户故事）

**Purpose**: `decides`/`scope` 数据层是 US1 召回与 US2 gate 的地基；缺失则召回第一步无法判相关性。对应 plan.md **[SUBAGENT-A]** 流。承载 **US3 数据层交付**（AC1/AC3）。

**CRITICAL**: US1/US2 实现不得在本阶段完成前开始（skill 自检与 gate 审计都依赖真实 `decides`/`scope` 数据）。

- [ ] T002 [P] [SUBAGENT-A] [US3] 扩展 ADR 模板：编辑 `docs/decisions/_template.md`，在既有 frontmatter 后新增 `decides`（一句话，决策对象+约束，<120 字）与 `scope`（path glob 列表）字段，附写作示导（对象/约束/长度规则）与反例（"我们选了事件驱动" / "见正文" / 超长论证），并引用 `contracts/adr-frontmatter.md` 质量判据。模板须提示：`supersedes ADR-NNNN` 时 `scope` 必须覆盖被取代者。（FR-001, US3 AC1/AC3）
- [ ] T003 [P] [SUBAGENT-A] [US3] 扩展 ADR 索引：编辑 `docs/decisions/INDEX.md`，新增 `decides` 摘要列，使 agent 可一次性扫描全部 accepted ADR 的相关性（Tier 0 语义源）。回填 0001-0005 的摘要（与 T004 回填内容一致）。（FR-003）
- [ ] T004 [P] [SUBAGENT-A] 回填 5 条 accepted ADR：逐文件为以下 ADR 填 `decides`（对象+约束 <120 字）+ `scope`（仓库相对 path glob，覆盖真实代码），每条独立 commit：
  - `docs/decisions/0001-adopt-adr-loop.md`
  - `docs/decisions/0002-protocol-based-di.md`（scope 示例：`src/vibe3/clients/protocols.py`、`src/vibe3/services/**` 等真实路径）
  - `docs/decisions/0003-runtime-loading-contract.md`（scope：`src/vibe3/runtime/**`）
  - `docs/decisions/0004-domain-flow-event-boundary.md`（decides 已有契约示导草稿：DomainEvent 禁止承担 flow 状态机判断；scope：`src/vibe3/models/domain_events.py`、`src/vibe3/models/flow.py`、`src/vibe3/domain/handlers/**`、`src/vibe3/runtime/**`）
  - `docs/decisions/0005-prompt-policy-skill-audit-evidence-model.md`
  **每条验证**：`decides` 含决策对象+约束词+<120 字；`scope` glob 在当前 worktree 至少命中 1 个现存路径（用 `ls`/`git ls-files` 核对）。（FR-002）

**Execution notes**: T002/T003/T004 改不同文件，可 [P] 并行或由 [SUBAGENT-A] 串行。T004 的 5 个 ADR 逐条 commit，便于单条 review/回滚。

**Checkpoint**（plan.md Human Checkpoint 1）: 数据层完成。人工核验 5 个 ADR 的 `decides` 质量（对象+约束、<120 字）与 `scope`（glob 覆盖真实代码）。获批准后再进入 US1/US2。

---

## Phase 3: User Story 1 — Planner 召回相关 ADR 并产 artifact (Priority: P1) MVP

**Goal**: planner 运行召回 skill，按 `decides` 语义 + `scope` 代码 glob 筛选 accepted ADR，只读命中项正文，产出可审计 artifact（对应 plan.md **[SUBAGENT-B]** 流）。
**Independent Test**: 给定触及 `src/vibe3/execution/` 的 issue，跑召回后 plan 出现完整 ADR-Consideration 节，且仅读命中项 body。

### 场景/样例先行（TDD-Scenario）

> 先写 failing 样例，再实现 skill 使其正确标记。

- [ ] T005 [TDD-Scenario] [SUBAGENT-B] 写自检黄金样例（先于 skill 实现）：在 `.claude/skills/adr-recall/examples/` 放：
  - 低质 `decides` 样例（`decides_quality_flags` 期望：missing_object / missing_constraint / too_long 各一）
  - 腐烂 `scope` 样例（`scope_rot_flags` 期望：missing_path — 指向不存在路径；supersede_gap — successor 未覆盖 predecessor scope）
  - 一个完整 artifact 样例（happy path，字段齐全，作 S6 输出对照）
  样例即 skill 自检判定的"黄金标准"，实现后须被 S3/S4 判定结果匹配。（FR-006, FR-007, SC-001, SC-004）

### 召回 skill 实现

- [ ] T006 [SUBAGENT-B] [US1] 实现召回 skill 主体 `.claude/skills/adr-recall/SKILL.md`：承载 `contracts/recall-checklist.md` 的 6 步状态机——
  - S1 读 `docs/decisions/INDEX.md` 的 `decides` 列，按 issue 语义（标题+描述+comments）标候选集
  - S2 取改动文件清单（`vibe3 inspect base`，只读复用），匹配候选 ADR 的 `scope` glob，升 applicable
  - S3 `decides` 质量自检（按 `contracts/adr-frontmatter.md` §质量判据，对照 T005 样例），产 `decides_quality_flags`
  - S4 `scope` 健康自检：R1 glob 展开 ≥1 现存路径；R2 supersede 链 successor scope ⊇ predecessor scope，产 `scope_rot_flags`（kind=missing_path/supersede_gap）
  - S5 **仅**读 applicable 候选正文（选择性，SC-001），抽取约束要点
  - S6 产 artifact（见 T007）
  skill 无状态，每次从头执行；不调用任何新 Python 命令（FR-004, FR-006, FR-007, FR-008）。
- [ ] T007 [SUBAGENT-B] [US1] 实现 artifact 产出（skill 的 S6）：按 `contracts/artifact.md` schema 填 plan.md 的 `## ADR Consideration` 节——`adr_snapshot_baseline`(branch+commit) / `evaluated_adrs`(全集) / `applicable` / `dismissed`+reason(必填，禁空豁免) / `self-check flags` / `supersede_proposals`。强制规范：零匹配时 `evaluated`=全集、`dismissed` 含全部+逐条理由（防假阴性，Edge Case #4）；平凡变更（错字/依赖升版）走豁免声明。（FR-005, FR-009, US1 AC1, US1 AC3, US1 AC4）
- [ ] T008 [REVIEW] [US1] review recall skill + 自检逻辑（plan.md [REVIEW] gate 1）：确认 S1-S6 与契约一致、自检判定匹配 T005 黄金样例、选择性不变量（读 body 数 ≤ accepted 总数）成立。

**Execution notes**: T005 先行（TDD-Scenario），T006/T007 依赖 T005 样例与 Phase 2 数据层。T006/T007 同文件可串行。T008 是 review 门。

**Checkpoint**（plan.md Human Checkpoint 2）: 召回 skill 完成。在一个真实触及 `src/vibe3/execution/` 或 `src/vibe3/domain/handlers/` 的 issue 上 dry-run 召回，确认 artifact 字段完整、选择性正确（不全量读 body，SC-001）、ADR-0004 因 scope 命中进 applicable。

---

## Phase 4: User Story 2 — Reviewer 审计 ADR 合规并阻断违规 (Priority: P1)

**Goal**: reviewer 审计 artifact 完整性/豁免理由/腐烂标记/是否违反 accepted ADR，违规给 BLOCK verdict，复用 FailedGate + `roadmap/rfc` 标签阻断（对应 plan.md **[SUBAGENT-C]** 流）。
**Independent Test**: 植入违反 ADR-0004 的 plan 且 artifact 空豁免 → review 给 BLOCK + 建议打 `roadmap/rfc`。

> **并行机会**：本阶段 gate 文本/接线任务（T009/T010/T012/T013）改不同文件，可与 Phase 3 的 skill 实现并行起草（[SUBAGENT-C] 与 [SUBAGENT-B] 并行）。但端到端验证 T014 须待 US1 skill (T006-T008) 与 US2 gate (T009-T011) 均完成。

### Review gate（门槛）

- [ ] T009 [P] [SUBAGENT-C] [US2] 编辑 `supervisor/policies/review.md`：在既有编号预审查清单中新增 "ADR 合规审计" 项 + BLOCK 规则——审计 artifact 字段约束（对照 `contracts/artifact.md` 字段约束表）：漏评 scope 命中的 accepted ADR / 空豁免 / 漏报已知腐烂 / plan 违反适用或被豁免的 accepted ADR → verdict=BLOCK → 喂入既有 FailedGate（`src/vibe3/orchestra/failed_gate.py`，只读复用）。reviewer 在 comment **建议**打 `roadmap/rfc`（单标签，由 `vibe-roadmap` 应用，reviewer 不直接打标）。（FR-010, FR-011, US2 AC1, US2 AC2, SC-003, SC-005）
- [ ] T010 [P] [SUBAGENT-C] [US2] 编辑 `skills/vibe-review-code/SKILL.md`：在 review flow 增 "审计 ADR-Consideration artifact" 步，指向 `supervisor/policies/review.md` 的 ADR 合规审计节。保留既有护栏（不发 PR / 不 merge / 不 label），artifact 缺失或违规时按 review.md 给 BLOCK。（FR-010）
- [ ] T011 [REVIEW] [US2] review gate 文本（plan.md [REVIEW] gate 3）：确认用词与 review.md 既有 PASS/MAJOR/BLOCK 契约一致，BLOCK 路径正确指向 FailedGate，`roadmap/rfc` 仅作建议（不越权打标）。

### Policy 接线（plan 阶段 advisory 入口）

- [ ] T012 [P] [SUBAGENT-C] 编辑 `supervisor/policies/plan.md`：将 §84 附近"- **检查 ADR 约束**：先读取 docs/decisions/INDEX.md…"改为"运行 `.claude/skills/adr-recall` skill + 产 ADR-Consideration artifact"。（FR-012）
- [ ] T013 [P] [SUBAGENT-C] 编辑 `skills/vibe-task/SKILL.md`（line 125 附近）与 `skills/vibe-roadmap/SKILL.md`（line 444 附近）：把"读 INDEX.md"类指令同步改为"运行 adr-recall skill + 产 artifact"。（FR-012）

### 端到端验证（TDD-Scenario）

- [ ] T014 [TDD-Scenario] [US2] 植入违规验证阻断（quickstart 场景 2）：构造一个让 DomainEvent handler 重新承担 flow 状态机判断的 plan（违反 ADR-0004 `decides`），其 artifact 把 ADR-0004 标 `Dismissed` 且 reason 留空。跑 review（`vibe3 review` 或 `vibe-review-code` skill）→ 期望 verdict=BLOCK、flow 被 FailedGate 阻断、comment 建议打 `roadmap/rfc`。证据存 issue comment。（FR-011, US2 AC1, US2 AC2, SC-003）

**Checkpoint**（plan.md Human Checkpoint 3）: 门槛+接线完成。植入违规 plan 确认 review 给 BLOCK + `roadmap/rfc` 建议，无静默放行。

---

## Phase 5: User Story 3 — ADR 作者维护 frontmatter 质量 + 治理收尾 (Priority: P2)

**Goal**: US3 数据层（模板/示导）已在 Phase 2 交付；本阶段完成 US3 端到端验证（自检标记低质/supersede 继承提示）与 constitution 治理增补。
**Independent Test**: 新建测试 ADR 不填 `decides` → 召回自检标记低质并反映 artifact。

- [ ] T015 [TDD-Scenario] [US3] US3 端到端验证：
  - 低质 decides 可见（quickstart 场景 3 的对偶）：构造 `decides: "我们选了事件驱动"` 的测试 ADR → 跑召回 → S3 标 `decides_quality_flags: missing_object/missing_constraint` 并反映 artifact。（US3 AC2）
  - supersede 继承缺口（quickstart 场景 5）：临时构造 ADR-9999 `supersedes ADR-0004` 但 `scope` 故意不覆盖 0004 某路径 → S4 标 `scope_rot_flags: supersede_gap`。（US3 AC3, Edge Case #2, SC-004）
  - 验证后删除测试 ADR。证据存 handoff/issue comment。
- [ ] T016 [SUBAGENT] 治理收尾（主 agent，不宜并行）：编辑 `.specify/memory/constitution.md`，增补 "principles（SOUL/CLAUDE/rules）↔ spec（per-feature）↔ ADR（cross-cutting）三层互补关系" 节，声明三者职责不重叠（单一事实原则）。按既有 semver 规则 MINOR bump（research.md §8）。（FR-013）

---

## Phase N: Polish & Cross-Cutting Concerns

**Purpose**: quickstart 场景化验收全覆盖 + 全 FR 复核。

- [ ] T017 [P] [SUBAGENT] 文档同步：确认 `docs/decisions/INDEX.md` 说明、`_template.md` 示导反映最终 schema；若有 ADR 作者指南文档，同步 `decides`/`scope` 写作规范。
- [ ] T018 quickstart 场景 1 + 4 验收：
  - 场景 1 Happy Path（触及 `src/vibe3/execution/` 的真实 issue）：召回产完整 artifact、ADR-0004 进 applicable、planner 仅读命中 body（SC-001, SC-002, US1 AC1, US1 AC2）。
  - 场景 4 零匹配（纯文档/CI 类 issue）：`applicable` 空、`evaluated` 仍全集、`dismissed` 含全部+逐条理由、reviewer 审计零匹配主张成立（Edge Case #4, US1 AC4）。
- [ ] T019 quickstart 场景 3 + 5 验收：
  - 场景 3 Scope Rot：临时把 ADR-0004 `scope` 改指不存在路径 → S4 标 missing_path 反映 artifact（SC-004）。事后还原。
  - 场景 5 Supersede 缺口：见 T015 构造的 ADR-9999 验证 supersede_gap 标记。
- [ ] T020 [REVIEW] 全 FR 逐项复核：对照 spec.md FR-001…FR-014 逐项标注承载任务与证据；确认 FR-014 边界（无新增 Python/引擎/embeddings）；确认 SC-001…SC-005 全部由场景验收支撑。结论与证据汇总到 issue comment。（HARD RULES #3）

**Execution notes**: T017-T019 可 [P]。T020 是合入前最终 review 门。

**Checkpoint**（plan.md Human Checkpoint 4）: 合入前。全 FR 复核通过、5 个 quickstart 场景可复现、SC 全部达标。

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: 契约锁定 → BLOCKS 全部
- **Foundational (Phase 2)**: 依赖 Setup；**BLOCKS** US1/US2（skill 自检与 gate 审计依赖真实 `decides`/`scope`）
- **US1 (Phase 3)**: 依赖 Foundational。skill 实现可与 US2 gate 文本并行起草
- **US2 (Phase 4)**: gate 文本/接线（T009/T010/T012/T013）可与 US1 并行；端到端 T014 依赖 US1 (T006-T008) + US2 gate (T009-T011)
- **US3 (Phase 5)**: T015 依赖 US1 skill 自检；T016 constitution 收尾无强依赖，宜最后
- **Polish (Phase N)**: 依赖 US1/US2/US3 全部完成

### Within Each User Story

1. [TDD-Scenario] 场景/样例先写（failing），再实现使其通过
2. 数据层（模板/回填）先于消费它的 skill 自检
3. skill 主体先于 artifact 产出
4. gate 文本先于端到端阻断验证
5. [REVIEW] 任务暂停等人工确认
6. 每个故事 checkpoint 通过后再进下一优先级

### Parallel Opportunities（对应 plan.md 三流）

- Phase 2 内 T002/T003/T004 [P]（不同文件）→ **[SUBAGENT-A]**
- Phase 3 skill（T005-T008）→ **[SUBAGENT-B]**；可与 Phase 4 gate/接线并行
- Phase 4 gate/接线（T009-T013）→ **[SUBAGENT-C]**
- constitution 增补（T016）由主 agent 收尾统一写（治理文本，不并行）
- 注：均为 markdown 小改动，并行收益有限；不并行按 A→B→C 串行亦可（plan.md）

---

## Superpowers Execution

### Execution Discipline by Marker

- **[TDD-Scenario]**: 本特性零 Python 的 TDD 适配。先写场景/黄金样例（须 failing 或期望可判），再实现，验证 skill 自检判定/ review verdict 与期望一致。非传统 Red-Green-Refactor。
- **[SUBAGENT]**: 若 `subagent-driven-development` 可用，按 A/B/C 三流派发；否则当前会话串行。
- **[REVIEW]**: 暂停，呈完成物给人工，等明确批准（T001 契约 / T008 skill / T011 gate 文本 / T020 全 FR）。
- **[P]**: 同 phase 内不同文件任务尽量并行。

### Checkpoint Protocol

每个 phase 边界（对应 plan.md 4 个人工 checkpoint）：
1. 汇报本阶段完成物
2. 跑 applicable 场景验收（quickstart 场景 或 TDD-Scenario 样例）
3. 报告验收结果（artifact / verdict / flag 输出作证据）
4. 询问 "Phase [N] 完成，进入 Phase [N+1]？"
5. 获明确批准后继续

---

## Notes

- 全部 enforcement 复用既有 FailedGate / BLOCK / `roadmap/rfc` 标签（SC-005，HARD RULES #15）
- 不新增 Python 命令层（FR-014，HARD RULES #16）；recall 以 `.claude/skills/adr-recall/` skill 承载
- 证据形态：artifact 输出 / review verdict / 自检 flag（HARD RULES #3），非 pytest 日志
- 每个任务或逻辑组完成后 commit（HARD RULES #5，走 feature 分支，禁 --no-verify）
- FR-014 延期项（Python 引擎/评分/embeddings/分层披露）等 ADR 数 >15-20 另立 feature，本期不做
