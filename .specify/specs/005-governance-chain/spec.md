# Feature Specification: Governance Chain Baseline

**Feature Branch**: `dev/issue-3299`

**Created**: 2026-07-03

**Status**: Draft (Baseline / Reverse Specification)

**Spec Mode**: 逆向规格化（Reverse Specification）。本 spec 描述 governance chain 子系统**当前代码的行为契约**，作为后续变更的行为参照基线。**不设计新功能、不改代码。**

**Input**: User description: "逆向规格化 governance-chain 模块的现有行为契约（baseline spec，非新功能设计）"

## Spec Mode 说明

本 spec 是 **baseline 行为契约**，描述"系统现在如何做治理观察、审计与策略合并"。真源：

- `supervisor/governance/*.md`（base 治理材料，跨项目通用）
- `.vibe/governance/*.md`（项目专属 governance overlay）
- `supervisor/policies/*.md`（base 策略材料，按 mode 注入）
- `.vibe/policies/*.md`（项目专属 policy overlay）
- `docs/decisions/0005-prompt-policy-skill-audit-evidence-model.md`（ADR-0005，4 层审计证据模型）
- `.claude/rules/*.md`（仓库长期规则）

**冲突处理**：当代码/材料现状与文档不一致时，本 spec 以材料现状为准并显式标注。**范围边界**：本 spec 不承载项目硬规则，仅引用 [SOUL.md](../../../SOUL.md)、[CLAUDE.md](../../../CLAUDE.md) §HARD RULES、[docs/decisions/INDEX.md](../../../docs/decisions/INDEX.md)、[.specify/memory/constitution.md](../../memory/constitution.md)。

**关联 spec**：与 [003-role-protocol](../003-role-protocol/spec.md) 协作——governance/supervisor 是非 label-triggered 角色（FR-010）；与 [002-dispatch-execution](../002-dispatch-execution/spec.md) 协作——governance/supervisor 走同步执行 + L2 temporary worktree（004 FR-001）。

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 三层策略合并（rules + supervisor-policies + .vibe overlay）(Priority: P1)

策略材料分三层：`.claude/rules/*`（仓库长期硬约束）> `supervisor/policies/*`（base，跨项目通用，按 plan/run/review mode 注入）+ `.vibe/policies/*`（项目专属 overlay，文件名匹配时自动 append）。三者由 prompt 组装时按层级合并。

**Why this priority**: 三层合并是 agent 运行时策略注入的契约核心；层级错乱或 overlay 机制失效将导致 agent 行为偏离项目约定。

**Independent Test**: 在 `.vibe/policies/run.md` 追加项目专属条款，触发 `vibe3 run`，验证组装后的 prompt 含 base + overlay 合并内容。

**Acceptance Scenarios**:

1. **Given** `supervisor/policies/run.md`（base）与 `.vibe/policies/run.md`（overlay）同时存在，**When** prompt 组装为 run mode，**Then** 二者按 base + overlay 顺序合并注入（overlay 追加在 base 之后）。
2. **Given** 仅 `supervisor/policies/plan.md` 存在、`.vibe/policies/plan.md` 不存在，**When** 组装 plan mode prompt，**Then** 只注入 base，不报错。
3. **Given** `.claude/rules/coding-standards.md` 与 `supervisor/policies/common.md` 对同一约束有不同表述，**When** 发生冲突，**Then** 以 `.claude/rules/*` 为权威（层级最高，见 [.claude/rules/README.md](../../../.claude/rules/README.md) 规则优先级）。

---

### User Story 2 - Roadmap Intake 三级审查（issue 分检）(Priority: P1)

governance scan agent 读取 `roadmap-intake.md`（base + `.vibe/governance/roadmap-intake.md` overlay）对 issue 做形式审查：非 task 识别、过时检查、反模式识别；通过后分配 assignee，由 `assignee-pool.md` 做内容判断（RFC/epic/split 路由）。

**Why this priority**: intake 是 issue 进入执行池的守门环节，"形式审查 vs 内容判断"的分层是契约核心（intake 不做深度内容判断）。

**Independent Test**: 对一个纯讨论 issue 运行 intake，验证被识别为非 task 剔除；对一个引用已移除模块的 issue 验证被识别为过时。

**Acceptance Scenarios**:

1. **Given** 一个纯讨论/提问 issue（无明确交付目标），**When** roadmap-intake 审查，**Then** 识别为非 task 并剔除（不纳入 assignee pool）。
2. **Given** 一个引用已移除模块/API 的 issue，**When** intake 审查，**Then** 识别为过时并剔除。
3. **Given** 一个违反 SOUL.md/CLAUDE.md 原则的 issue，**When** intake 审查，**Then** 识别为反模式并剔除。
4. **Given** 一个通过形式审查的 issue，**When** intake 完成，**Then** 分配 assignee，路由到 assignee-pool 做内容判断（RFC/epic/split），intake **不**做深度内容判断。

---

### User Story 3 - 4 层审计证据模型（observation → suggestion → report → decision）(Priority: P1)

governance 审计链遵循 ADR-0005 的 4 层证据模型：`observation → suggestion → report → decision`。suggestion 含两类来源（`runtime_observation` 系统性假设 + `code_auditor` 静态代码审计），二者 MUST 先经 audit-report 统一审计，decision 不直接消费原始 code-auditor 发现。

**Why this priority**: 4 层模型是治理审计的可追溯证据链，"decision 不直接消费原始发现"是防止越级误判的硬约束（ADR-0005）。

**Independent Test**: 构造一个 code-auditor 原始发现，验证它经 audit-report 转化为 report 后才被 audit-decision 消费。

**Acceptance Scenarios**:

1. **Given** observation cluster 产生系统性假设，**When** 进入审计链，**Then** 经 audit-observation → audit-suggestion（作为 `runtime_observation`）→ audit-report → audit-decision 逐层升华。
2. **Given** code-auditor 产生静态代码质量发现，**When** 进入审计链，**Then** 作为 `code_auditor` 类 suggestion，先经 audit-report 统一审计，**不**直接被 audit-decision 消费。
3. **Given** 任一层 evidence，**When** 流转，**Then** 每层产出可追溯的审计记录（observation/suggestion/report/decision 各有对应 governance 材料与产物）。

---

### User Story 4 - Governance Scan vs Supervisor/Apply 角色分工 (Priority: P2)

governance scan 是无临时 worktree 的观察/派单 agent（使用 governance 材料）；supervisor/apply 是有临时 worktree 的治理执行 agent（执行 label/comment/close/recreate 及文档/测试类 L2 小改动，禁止主代码修改）。runtime orchestra 是系统层（heartbeat/event-bus），不含业务判断。

**Why this priority**: 三者（governance material / runtime orchestra / supervisor-apply）独立性是契约核心，混淆将导致治理越权或系统层被污染。

**Independent Test**: 验证 governance scan 不持有 worktree、不执行写动作；验证 supervisor/apply 持有 L2 temporary worktree 且只做 L2 小改动。

**Acceptance Scenarios**:

1. **Given** governance scan 任务，**When** 运行，**Then** 无临时 worktree（纯观察/派单），只产出建议/路由，不直接修改 issue 现场或主代码。
2. **Given** supervisor/apply 任务，**When** 运行，**Then** 持有 L2 temporary worktree，可执行 label/comment/close/recreate 及文档/测试类 L2 小改动，**禁止**主代码修改。
3. **Given** runtime orchestra（heartbeat/event-bus），**When** 运行，**Then** 只做定时触发与事件分发，**不含**业务判断逻辑（业务判断在 governance/apply 层）。

---

### User Story 5 - Governance 材料 overlay 机制 (Priority: P2)

`.vibe/governance/<material>.md` 按文件名匹配自动 append 到 `supervisor/governance/<material>.md`，机制与 `.vibe/policies/` 一致。

**Why this priority**: overlay 机制是项目定制 governance 而不修改上游 base 的契约路径（HARD RULES #15 最短路径优先的体现）。

**Independent Test**: 在 `.vibe/governance/roadmap-intake.md` 追加项目专属 intake 规则，验证 governance scan 使用 roadmap-intake 材料时含 overlay 内容。

**Acceptance Scenarios**:

1. **Given** `supervisor/governance/roadmap-intake.md`（base）与 `.vibe/governance/roadmap-intake.md`（overlay），**When** governance scan 使用 roadmap-intake 材料，**Then** 注入 base + overlay 合并内容。
2. **Given** 仅 base 存在、overlay 不存在，**When** 使用该材料，**Then** 只注入 base，不报错。

---

### User Story 6 - 审计门与 prompt 模板治理 (Priority: P3)

governance prompt 模板与审计门是治理链路的确定性保障：dry-run 条件指令需无意义化清理（PR #3291）；审计门（qualify gate / review kernel）在不同阶段强制对应检查。

**Why this priority**: prompt 模板与审计门的正确性是 governance 链路可信的基础；无效条件指令会误导 agent。

**Independent Test**: 检查 governance prompt 模板无 dry-run 无意义条件指令（PR #3291 已修复）。

**Acceptance Scenarios**:

1. **Given** governance prompt 模板，**When** 审查，**Then** 无无意义的 dry-run 条件指令（PR #3291 已修复，baseline 保留此约束）。
2. **Given** 治理链路各阶段（intake/audit/dispatch），**When** 经过对应审计门（qualify gate / review kernel / no-op gate），**Then** 强制对应检查（分别见 002 FR-006、003 FR-011、002 FR-004）。

---

### Edge Cases

- **三层边界不可混装**：`.claude/rules/*`（仓库长期） vs `supervisor/policies/*`（mode 策略） vs governance materials（治理观察）—— 不要把仓库级规则写进 policy，也不要把 mode-specific 策略塞回 rules（见 [supervisor/policies/README.md](../../../supervisor/policies/README.md)）。
- **overlay 文件名必须精确匹配**：`.vibe/policies/plan.md` 只 append 到 `supervisor/policies/plan.md`，不跨文件生效。
- **intake 不做深度内容判断**：架构方向、RFC/epic 需求、优先级、依赖深度决策由 assignee-pool 层负责，intake 越界是契约违反。
- **code-auditor 发现不越级**：原始 code-auditor 发现 MUST 经 audit-report，decision 直接消费属契约违反（ADR-0005）。
- **supervisor/apply 的 L2 限制**：可做文档/测试修补类 L2 小改动，**禁止**主代码修改；越权属契约违反。
- **governance 材料清单**：roadmap-intake、assignee-pool、audit-observation、audit-suggestion、audit-report、audit-decision、code-auditor、cron-supervisor（8 个 base 材料）。
- **governance/supervisor 非 label-triggered**：不参与 LABEL_DISPATCH_ROLES（见 003 FR-010），由 CLI/scheduled 触发。

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: 策略材料 MUST 分三层并按层级合并：`.claude/rules/*`（权威，最高）> `supervisor/policies/*` + `.vibe/policies/*` overlay > governance materials。冲突时以高层级为准。
- **FR-002**: `.vibe/policies/<mode>.md` MUST 按文件名匹配自动 append 到 `supervisor/policies/<mode>.md`（mode ∈ {common, plan, run, review}）；overlay 缺失时只注入 base。
- **FR-003**: `.vibe/governance/<material>.md` MUST 按文件名匹配自动 append 到 `supervisor/governance/<material>.md`，机制与 policies overlay 一致。
- **FR-004**: roadmap-intake（base + overlay）MUST 对 issue 做形式审查：非 task 识别、过时检查、反模式识别；**不**做深度内容判断（架构/RFC/优先级/依赖深度决策）。
- **FR-005**: 通过 intake 形式审查的 issue MUST 分配 assignee 并路由到 assignee-pool 做内容判断（RFC/epic/split 路由）。
- **FR-006**: 审计链 MUST 遵循 ADR-0005 的 4 层证据模型：`observation → suggestion → report → decision`，每层有对应 governance 材料与可追溯产物。
- **FR-007**: suggestion MUST 含两类来源（`runtime_observation` 系统性假设 + `code_auditor` 静态代码审计）；二者 MUST 先经 audit-report 统一审计，audit-decision **不**直接消费原始 code-auditor 发现。
- **FR-008**: governance scan MUST 为无临时 worktree 的观察/派单 agent，只产出建议/路由，不直接修改 issue 现场或主代码。
- **FR-009**: supervisor/apply MUST 持有 L2 temporary worktree（见 004 FR-001），可执行 label/comment/close/recreate 及文档/测试类 L2 小改动，**禁止**主代码修改。
- **FR-010**: runtime orchestra（heartbeat/event-bus）MUST 只做定时触发与事件分发，**不含**业务判断逻辑。
- **FR-011**: governance 材料体系 MUST 包含 8 个 base 材料：roadmap-intake、assignee-pool、audit-observation、audit-suggestion、audit-report、audit-decision、code-auditor、cron-supervisor。
- **FR-012**: governance prompt 模板 MUST 无无意义的 dry-run 条件指令（PR #3291 已修复，baseline 保留此约束）。
- **FR-013**: governance 与 supervisor MUST NOT 出现在 `LABEL_DISPATCH_ROLES`（见 003 FR-010），由 CLI/scheduled 触发，走同步执行（见 002 FR-008）。
- **FR-014**: 三类材料（`.claude/rules/*` 仓库规则 / `supervisor/policies/*` mode 策略 / governance materials 治理观察）MUST 各司其职，不互相混装。

### Key Entities *(include if feature involves data)*

- **Governance Materials**（`supervisor/governance/*.md`）：8 个 base 治理材料，定义 governance agent 角色与行为边界。
- **Policy Materials**（`supervisor/policies/*.md`）：common/plan/run/review/test-strategy/kiro-integration，按 mode 注入。
- **.vibe overlay**（`.vibe/policies/*.md` + `.vibe/governance/*.md`）：项目专属扩展，按文件名匹配 append。
- **4 层审计证据**（ADR-0005）：observation / suggestion（runtime_observation + code_auditor）/ report / decision。
- **assignee issue pool**：执行池，由 intake 形式审查通过后入池，由 assignee-pool 做内容路由。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 三层策略合并可观测：`.vibe/policies/<mode>.md` overlay 存在时，组装后的 prompt 含 base + overlay 内容（可抓取 prompt 验证）。
- **SC-002**: roadmap-intake 对纯讨论/过时/反模式 issue 的剔除行为有对应测试覆盖（可回归）。
- **SC-003**: 4 层审计证据模型的每一层流转有可追溯产物（observation/suggestion/report/decision 各有对应输出）。
- **SC-004**: governance scan 不持有 worktree、不执行写动作；supervisor/apply 持有 L2 worktree 且仅做 L2 小改动（可测试验证边界）。
- **SC-005**: code-auditor 原始发现经 audit-report 转化后才被 audit-decision 消费（不越级，可测试）。
- **SC-006**: governance prompt 模板中无 dry-run 无意义条件指令（PR #3291 约束，可静态检查）。

## Assumptions

- **baseline 范围假设**：本 spec 覆盖三层策略合并、governance 材料体系、4 层审计证据模型、scan vs apply 角色分工、overlay 机制、审计门与 prompt 治理。**不**覆盖 role 触发协议（见 003）、dispatch 内部（见 002）、worktree 物理管理（见 004）。
- **权威层级假设**：`SOUL.md > CLAUDE.md > .claude/rules/* > supervisor/policies + .vibe overlay`；本 spec 描述合并机制，不复述权威内容（constitution 原则 II）。
- **ADR 假设**：4 层审计证据模型由 [ADR-0005](../../../docs/decisions/0005-prompt-policy-skill-audit-evidence-model.md) 定义；本 spec 引用其结论，不重新论证。
- **PR #3291 假设**：governance prompt 模板的 dry-run 无意义条件指令已清理；baseline 保留"无此类指令"的约束。
- **scan/apply 分离假设**：governance scan（观察）与 supervisor/apply（执行）的 worktree 持有与写权限差异由 [supervisor/governance/assignee-pool.md](../../../supervisor/governance/assignee-pool.md) 等材料定义，本 spec 描述契约不复述材料内容。
