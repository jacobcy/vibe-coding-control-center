# Feature Specification: Handoff Protocol Baseline

**Feature Branch**: `dev/issue-3299`

**Created**: 2026-07-03

**Status**: Draft (Baseline / Reverse Specification)

**Spec Mode**: 逆向规格化（Reverse Specification）。本 spec 描述 handoff 子系统**当前代码的行为契约**，作为后续变更的行为参照基线。**不设计新功能、不改代码。**

**Input**: User description: "逆向规格化 handoff-protocol 模块的现有行为契约（baseline spec，非新功能设计）"

## Spec Mode 说明

本 spec 是 **baseline 行为契约**，描述"系统现在如何在 agent/session 之间传递短期上下文"。真源：

- `src/vibe3/services/handoff/*`（service / storage / resolution / validation / status / external_events）
- `src/vibe3/commands/handoff.py`（CLI 命令层）
- [docs/standards/v3/handoff-governance-standard.md](../../../docs/standards/v3/handoff-governance-standard.md)（治理权威）
- [docs/standards/v3/handoff-store-standard.md](../../../docs/standards/v3/handoff-store-standard.md)（store schema 权威）

**冲突处理**：当代码现状与标准文档不一致时，本 spec 以代码行为为准并显式标注。**范围边界**：本 spec 不承载项目硬规则，仅引用 [CLAUDE.md](../../../CLAUDE.md) §HARD RULES #7（handoff 边界）、[docs/standards/glossary.md](../../../docs/standards/glossary.md)、[.specify/memory/constitution.md](../../memory/constitution.md)。

**关联 spec**：与 [001-flow-lifecycle](../001-flow-lifecycle/spec.md) 协作——handoff 不复述 flow 状态，仅补充解释；与 [003-role-protocol](../003-role-protocol/spec.md) 协作——kind→actor 字段映射对齐角色（planner/executor/reviewer/manager）。

## 核心定位（诚实记录）

handoff **不是真源**，是 agent/session/skill 之间的**短期上下文缓冲**。它传递：Achievements / Blockers / Findings / Next Steps / Key Files。**不得替代** SQLite store、`vibe3` CLI 实时输出、git 现场事实（HARD RULES #7，治理真源在 handoff-governance-standard §2-3，本 spec 引用不复述）。

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 两层存储：SQLite 责任链 + Markdown Buffer (Priority: P0)

handoff 固定两层：SQLite（`flow_state` 表，最小责任链：plan/run/review ref + planner/executor/reviewer/manager actor + blocked/next_step）+ Shared Markdown Buffer（`current.md`，轻量结构化交接）。SQLite 是责任链真源；Markdown 是补充缓冲（store-standard §1, §4-5）。

**Why this priority**: 两层分工是 handoff 系统的存储契约核心；混淆将导致 Markdown 膨胀为第二真源。

**Independent Test**: 写入一条 plan handoff，验证 `flow_state.plan_ref` + `planner_actor` 更新且 `flow_events` 记一条 `handoff_plan`；同时验证 `current.md` 含对应 section。

**Acceptance Scenarios**:

1. **Given** 一条 plan handoff 写入，**When** `HandoffService` 处理，**Then** `flow_state.plan_ref` 与 `planner_actor` 更新，`flow_events` 记录 `handoff_plan`，`updated_at` 刷新。
2. **Given** `current.md` 缓冲，**When** 读取，**Then** 含固定 section（Meta/Summary/Findings/Blockers/Next Actions/Key Files/Evidence Refs），但**不**含 issue/PR 正文镜像或 plan/run/review 全文（store-standard §5.2 禁止）。
3. **Given** SQLite 与 Markdown 内容冲突，**When** 仲裁，**Then** 以 SQLite 责任链为准（Markdown 不可覆盖责任链字段）。

---

### User Story 2 - CLI-only 访问边界（严禁直接文件系统访问）(Priority: P0)

`.git/vibe3/handoff/` 目录及其内容**严禁**任何 agent/skill 直接通过文件系统 API 访问（governance-standard §2 硬禁令）。所有操作 MUST 通过 `vibe3 handoff` CLI。Worktree 隔离环境下直接访问会被 external_directory 权限拒绝。

**Why this priority**: CLI-only 是多 worktree 权限一致性的硬约束；绕过将破坏访问治理。

**Independent Test**: 在 worktree 中尝试 `cat .git/vibe3/handoff/<branch>/current.md`，验证被权限拒绝；改用 `vibe3 handoff show` 验证成功。

**Acceptance Scenarios**:

1. **Given** agent 需读取 handoff，**When** 尝试直接 read_file/cat `.git/vibe3/handoff/...`，**Then** 被文件系统权限拒绝（external_directory 限制）。
2. **Given** 同一需求，**When** 使用 `vibe3 handoff show <target>`，**Then** CLI 代理访问成功返回内容。
3. **Given** agent 需写入 handoff，**When** 使用 `vibe3 handoff append <content>`，**Then** CLI 代理写入 `current.md`（追加轻量更新）。

---

### User Story 3 - 三命名空间 target 解析（@key / relative / abs）(Priority: P0)

`vibe3 handoff show <target>` 的 `<target>` 支持三命名空间（CLAUDE.md §Context And File Hygiene）：`@key`（共享 artifact，含 `@current`/`@plan`/`@report`/`@audit`/`@vibe/<path>` 特殊语义）/ `relative/path`（canonical worktree ref，需 `--branch`）/ `/abs/path`（调试 fallback）。

**Why this priority**: 命名空间解析是 handoff 寻址的核心契约，错配将导致跨 worktree 引用失败。

**Independent Test**: 对三种 target 各调用 `handoff show`，验证分别解析到共享 artifact、worktree 相对文档、绝对路径。

**Acceptance Scenarios**:

1. **Given** target `@task-xxx/run-yyy.md`，**When** `handoff show`，**Then** 解析为 `.git/vibe3/handoff/` 下的共享 artifact（忽略 `--branch`）。
2. **Given** target `@current --branch <b>`，**When** show，**Then** 解析为 `<b>` 的 per-branch `current.md`。
3. **Given** target `@plan --branch <b>`，**When** show，**Then** 从 `flow_state.plan_ref` 取值解析。
4. **Given** target `@vibe/<path>`，**When** show，**Then** 解析到 vibe3 installation materials，并经 path traversal 校验（含 `..` 或非法字符抛 `ValueError`）。
5. **Given** target `docs/reports/x.md --branch <b>`（relative），**When** show，**Then** 解析为 `<b>` worktree 的 canonical 文档。
6. **Given** target `/abs/path`，**When** show，**Then** 直接读绝对路径（调试 fallback）。

---

### User Story 4 - kind 规范化与字段映射（legacy 兼容）(Priority: P1)

handoff kind 经 `_normalize_kind` 归一化：legacy `report`→`run`、`audit`→`review`（`_LEGACY_KIND_ALIASES`）。canonical kind 映射到 DB ref 列（plan→plan_ref / run→report_ref / review→audit_ref / indicate→indicate_ref）与 actor 列（plan→planner_actor / run→executor_actor / review→reviewer_actor / indicate→manager_actor）。

**Why this priority**: legacy 兼容与字段映射是数据一致性的核心；错列将污染责任链。

**Independent Test**: 用 legacy kind `report` 写入，验证归一化为 `run` 后写入 `report_ref` + `executor_actor`，且 event type 记录兼容名。

**Acceptance Scenarios**:

1. **Given** kind `report`（legacy），**When** 写入，**Then** `_normalize_kind` 归一化为 `run`，写入 `report_ref`（DB 列名保留历史）+ `executor_actor`。
2. **Given** kind `audit`（legacy），**When** 写入，**Then** 归一化为 `review`，写入 `audit_ref` + `reviewer_actor`。
3. **Given** kind `indicate`，**When** 写入，**Then** 写入 `indicate_ref` + `manager_actor`（manager 角色专属）。
4. **Given** 任意 kind 写入，**When** 成功，**Then** `flow_events` 记录对应 event（`handoff_plan` / `handoff_report`(canonical) / `handoff_run`(backward-compat) / `handoff_audit` / `handoff_indicate`）。

---

### User Story 5 - authoritative ref 校验（防 temp/logs 与越界）(Priority: P1)

`validate_authoritative_ref` 强制：plan/report/audit/run/review kind 的 ref MUST 指向 agent worktree 内 canonical 文档，**禁止**指向 `temp/logs/`，**禁止**越出 worktree（path traversal 防护）。

**Why this priority**: authoritative ref 是责任链的导航锚点；指向日志或越界路径会破坏可追溯性（store-standard §8 路径原则）。

**Independent Test**: 分别用 `temp/logs/x.log`、worktree 外路径、worktree 内 canonical 文档作为 ref 写入，验证前两者抛 `UserError`、后者通过。

**Acceptance Scenarios**:

1. **Given** ref 指向 `temp/logs/...`，**When** 写入 authoritative kind，**Then** 抛 `UserError`（execution logs 不允许进入 authoritative ref）。
2. **Given** ref 越出 agent worktree，**When** 写入，**Then** 抛 `UserError`（必须 stay inside agent worktree）。
3. **Given** ref 指向 worktree 内 canonical 文档（如 `.agent/plans/x.md`），**When** 写入，**Then** 通过校验，登记到对应 `_ref` 列。

---

### User Story 6 - 读取优先级与维护义务 (Priority: P1)

读取 handoff 前必须先核查真源（flow show / task status / check / git status），handoff 仅作解释性补充（governance-standard §3-5）。优先级固定：共享真源（SQLite + CLI 实时）> 现场事实（git/worktree/PR）> Handoff Buffer。读取后发现过时 MUST 修正或标记（维护义务）。

**Why this priority**: 优先级与维护义务是防止 handoff 漂移成"事实副本"的治理核心。

**Independent Test**: 构造 handoff 内容与 git 现场冲突的场景，验证以现场为准；读取后验证维护义务触发（修正或标记过时）。

**Acceptance Scenarios**:

1. **Given** handoff 内容与 git 现场冲突，**When** 仲裁，**Then** 以现场事实为准（handoff 不可覆盖或伪造事实）。
2. **Given** agent 读取 handoff，**When** 发现与当前事实不一致，**Then** MUST 执行修正或标记过时（不允许明知过时却不修正）。
3. **Given** flow 对应 PR 已 merged，**When** 写 handoff，**Then** 只允许补记交付证据/审计/follow-up；新需求 MUST 进新 issue（禁止写入旧 plan）。

---

### Edge Cases

- **`@vibe/<path>` path traversal 防护**：含 `..` 抛 `ValueError`，含非法字符抛 `ValueError`，空 path 抛 `ValueError`（resolution.py 校验）。
- **`failed_reason` 字段已废弃**：store-standard §4.1 标注优先用 `blocked_reason`（代码保留兼容）。
- **`issue_role` 约束**：`flow_issue_links` 每 branch 只能一个 `task`、可多个 `related`/`dependency`（store-standard §4.2，唯一索引保障）。
- **event_type 双轨**：agent 主动写入记 `handoff_audit`；系统被动写入记 `audit_recorded`（store-standard §8）。
- **JSON 边界**：JSON 只允许 CLI `--json` 输出/调试/测试 fixture，**不允许**作为正式持久化主存储（store-standard §10）。
- **handoff 不承担生命周期真源**：branch/PR/issue 生命周期仍由 git/gh 承担，handoff 只记本地 execution context。

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: handoff MUST 采用两层存储：SQLite（`flow_state` 责任链 + `flow_issue_links` + `flow_events`）+ Shared Markdown Buffer（`current.md`）；SQLite 是责任链真源，Markdown 是补充缓冲。
- **FR-002**: `.git/vibe3/handoff/` 及其内容 MUST ONLY 通过 `vibe3 handoff` CLI 访问；直接文件系统 API 访问 MUST 被权限拒绝（governance-standard §2）。
- **FR-003**: `handoff show <target>` MUST 支持三命名空间：`@key`（含 `@current`/`@plan`/`@report`/`@audit`/`@vibe/<path>`）/ `relative/path`（需 `--branch`）/ `/abs/path`（调试 fallback）。
- **FR-004**: `@vibe/<path>` 解析 MUST 强制 path traversal 校验：含 `..`、非法字符或空 path 抛 `ValueError`。
- **FR-005**: kind MUST 经 `_normalize_kind` 归一化：legacy `report`→`run`、`audit`→`review`；canonical kind 映射 DB ref 列（plan→plan_ref / run→report_ref / review→audit_ref / indicate→indicate_ref）。
- **FR-006**: kind MUST 映射 actor 列：plan→planner_actor / run→executor_actor / review→reviewer_actor / indicate→manager_actor；actor 字段使用 `agent/model` 形态（如 `codex/gpt-5.4`）。
- **FR-007**: 写入 plan/run/review/indicate handoff MUST 在 `flow_events` 记录对应 event（含 canonical `handoff_report` 与 backward-compat `handoff_run` 双名）。
- **FR-008**: authoritative kind（plan/report/audit/run/review）的 ref MUST 经 `validate_authoritative_ref`：禁止指向 `temp/logs/`、禁止越出 agent worktree，违者抛 `UserError`。
- **FR-009**: 读取优先级 MUST 固定：共享真源（SQLite + CLI 实时）> 现场事实（git/worktree/PR）> Handoff Buffer；handoff 仅作解释性补充，不可覆盖事实。
- **FR-010**: agent 读取 handoff 后若发现与事实不一致，MUST 修正 buffer 或标记过时（维护义务，governance-standard §5）。
- **FR-011**: flow 对应 PR merged 后，handoff ONLY 允许补记交付证据/审计/follow-up；新需求 MUST 进新 issue，禁止写入旧 plan（governance-standard §6）。
- **FR-012**: `current.md` MUST 使用固定 section 模板（Meta/Summary/Findings/Blockers/Next Actions/Key Files/Evidence Refs），**禁止**记录 issue/PR 正文镜像或 plan/run/review 全文（store-standard §5）。
- **FR-013**: `flow_issue_links.issue_role` MUST 仅允许 `task`/`related`/`dependency`；每 branch 最多一个 `task`（唯一索引保障）。
- **FR-014**: JSON MUST NOT 作为正式持久化主存储；仅允许 CLI `--json` 输出/调试/测试 fixture（store-standard §10）。

### Key Entities *(include if feature involves data)*

- **HandoffService**：handoff 业务主入口，封装 kind 归一化、字段映射、event 记录、authoritative ref 校验。
- **HandoffStorage**：文件系统操作（`get_handoff_dir` / `ensure_current_handoff`），路径解析基于 `get_git_common_dir`。
- **resolution.py**：target 命名空间解析（`@key` / `@vibe/<path>` / relative / abs），含 path traversal 防护。
- **validate_authoritative_ref**：authoritative ref 边界校验（temp/logs 拒绝 + worktree 越界拒绝）。
- **flow_state 表**：责任链主表（branch 主键，含 plan/run/review/indicate ref + 4 actor + blocked/next_step + flow_status + transition_count + deleted_at 软删除）。
- **flow_events 表**：审计辅助表（最小事件，不记业务正文）。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 写入 plan/run/review/indicate handoff 后，`flow_state` 对应 ref+actor 列更新、`flow_events` 记一条 event、`updated_at` 刷新（可机器验证）。
- **SC-002**: 直接文件系统访问 `.git/vibe3/handoff/...` 被权限拒绝；`vibe3 handoff show/append` 经 CLI 代理成功（访问边界可测试）。
- **SC-003**: 三命名空间 target 各有独立解析路径，`@vibe/<path>` 含 path traversal 时抛 `ValueError`（命名空间解析可测试）。
- **SC-004**: legacy kind `report`/`audit` 归一化为 `run`/`review` 后写入正确 DB 列（兼容性可测试）。
- **SC-005**: authoritative ref 指向 `temp/logs/` 或越出 worktree 时抛 `UserError`（边界校验可测试）。
- **SC-006**: `flow_issue_links` 每 branch 多于一个 `task` role 时被唯一索引拒绝（约束可测试）。

## Assumptions

- **baseline 范围假设**：本 spec 覆盖 handoff 两层存储、CLI-only 访问、三命名空间、kind 规范化与字段映射、authoritative ref 校验、读取优先级与维护义务。**不**覆盖 flow 状态机语义（见 001）、role 触发（见 003）、handoff.db 的 SQLite schema 细节（store-standard §4 权威，本 spec 引用结论）。
- **真源层级假设**：handoff 不是真源，治理真源在 [handoff-governance-standard.md](../../../docs/standards/v3/handoff-governance-standard.md) 与 [CLAUDE.md](../../../CLAUDE.md) §HARD RULES #7，本 spec 引用不复述。
- **legacy 兼容假设**：`report`/`audit` 作为 legacy kind 别名保留，归一化为 canonical `run`/`review`；DB 列名 `report_ref`/`audit_ref` 保留历史命名不重命名。
- **`failed_reason` 废弃假设**：store-standard §4.1 标注 `failed_reason` 已废弃，优先 `blocked_reason`；代码保留兼容，baseline 不主动移除。
- **路径分类假设**：`temp/logs/...` 只允许 `log_path`/runtime session；`.git/vibe3/handoff/...` 只允许共享 store/artifact；二者均不进入 authoritative ref（store-standard §2, §8）。
