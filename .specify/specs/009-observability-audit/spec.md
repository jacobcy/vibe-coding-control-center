# Feature Specification: Observability & Audit Baseline

**Feature Branch**: `dev/issue-3299`

**Created**: 2026-07-03

**Status**: Draft (Baseline / Reverse Specification)

**Spec Mode**: 逆向规格化（Reverse Specification）。本 spec 描述 observability 子系统**当前代码的行为契约**，作为后续变更的行为参照基线。**不设计新功能、不改代码。**

**Input**: User description: "逆向规格化 observability-audit 模块的现有行为契约（baseline spec，非新功能设计）"

## Spec Mode 说明

本 spec 是 **baseline 行为契约**，描述"系统现在如何记录结构化日志、审计、事件、trace 与降级状态"。真源：

- `src/vibe3/observability/*.py`（5 模块：logger / audit / orchestra_log / degraded_mode / trace_method）
- `src/vibe3/observability/__init__.py`（公开 API 契约）

**冲突处理**：当代码现状与文档不一致时，本 spec 以代码行为为准并显式标注。**范围边界**：本 spec 不承载项目硬规则，仅引用 [CLAUDE.md](../../../CLAUDE.md) §Context And File Hygiene（日志保留）、[.claude/rules/modularity-standards.md](../../../.claude/rules/modularity-standards.md)、[.specify/memory/constitution.md](../../memory/constitution.md)。

**关联 spec**：与 [005-governance-chain](../005-governance-chain/spec.md) 协作——observability 提供 `AuditLogger` / `append_governance_event` 等记录基础设施，005 的治理审计链消费这些设施；005 描述 4 层证据模型**语义**（observation→suggestion→report→decision），本 spec 描述**记录机制**。与 [002-dispatch-execution](../002-dispatch-execution/spec.md) 协作——`append_orchestra_event` 记录 dispatch 事件。

**诚实记录**：observability **无专属标准文档**（`audit-evidence-model-standard.md` 属 005 语义层），行为契约从代码公开 API 提取。

## 核心定位

observability 是**横切关注点**（cross-cutting concern），为所有层（clients / services / execution / domain / governance）提供可观测性基础设施：结构化日志、审计记录、事件追加、方法级 trace、降级模式管理。它**不承载业务判断**，只提供记录与查询能力。

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 结构化日志（loguru + 领域绑定）(Priority: P0)

`setup_logging()` 初始化 loguru 结构化日志；日志通过 `logger.bind(domain=..., action=..., branch=...)` 绑定领域上下文。`logs_root()` 提供日志根路径。日志保留策略由调用方决定（session 销毁后日志保留供排查，见 CLAUDE.md §Context And File Hygiene）。

**Why this priority**: 结构化日志是所有可观测性的基础；领域绑定让日志可按 domain/action 检索。

**Independent Test**: 调用 `logger.bind(domain="handoff", action="write").info(...)`，验证日志输出含绑定字段。

**Acceptance Scenarios**:

1. **Given** app 启动，**When** `setup_logging()` 调用，**Then** loguru 配置完成，后续 `logger.info/error` 可用。
2. **Given** 业务日志，**When** `logger.bind(domain="dispatch", action="enqueue", branch=...)`，**Then** 输出含 domain/action/branch 结构化字段。
3. **Given** `logs_root()`，**When** 调用，**Then** 返回日志根路径（兼容 bare-repo + linked-worktree）。

---

### User Story 2 - 审计日志（AuditEntry / AuditLogger）(Priority: P0)

`AuditEntry` 是审计记录数据结构，`AuditLogger` 写入审计日志。审计是治理链（005）的记录底座——4 层证据模型（observation/suggestion/report/decision）的每一层通过 `AuditLogger` 落盘。

**Why this priority**: 审计是可追溯性的硬需求；AuditLogger 聚合审计条目，供 005 治理审计链与下游消费。

**诚实记录**：`AuditLogger` 在内存维护 `_entries: list[AuditEntry]`（聚合），**不直接写文件**；持久化落盘由消费方（治理链 / 事件日志 append 函数）负责。

**Independent Test**: 构造 `AuditEntry`，调用 `AuditLogger.log(entry)`，验证写入对应审计日志文件。

**Acceptance Scenarios**:

1. **Given** `AuditEntry`（含 actor / action / detail / timestamp），**When** `AuditLogger.log(entry)`，**Then** 条目追加到内存 `_entries` 列表（聚合，供消费方取用）。
2. **Given** 005 的 4 层证据流转，**When** 每层产出，**Then** 经 `AuditLogger` 聚合 + `append_*_event` 落盘（005 消费 009 基础设施）。
3. **Given** 审计日志路径，**When** 查询，**Then** 含完整 actor/action/detail/timestamp（可追溯）。

---

### User Story 3 - 分类事件日志（governance / orchestra / supervisor / tick）(Priority: P0)

事件日志按来源分类，各有独立目录与 events_log：`append_governance_event` / `append_orchestra_event` / `append_supervisor_event`（governance/orchestra/supervisor 三类）+ tick 日志（`tick_log_path`）。路径辅助：`governance_log_dir` / `orchestra_log_dir` / `supervisor_log_dir` / `tick_log_dir` / `governance_scans_dir` / `governance_dry_run_dir` / `issues_log_dir`。

**Why this priority**: 分类事件日志是按角色/来源隔离审计数据的核心；混装将导致治理/调度/监控数据互相污染。

**Independent Test**: 分别调用三类 append 函数，验证写入各自独立的事件日志文件。

**Acceptance Scenarios**:

1. **Given** governance scan 事件，**When** `append_governance_event(...)`，**Then** 写入 `governance_events_log_path()` 对应文件。
2. **Given** orchestra dispatch 事件，**When** `append_orchestra_event(...)`，**Then** 写入 `orchestra_events_log_path()`。
3. **Given** supervisor 监控事件，**When** `append_supervisor_event(...)`，**Then** 写入 `supervisor_events_log_path()`。
4. **Given** 需分隔连续 orchestra run，**When** `append_orchestra_run_separator()`，**Then** 写入分隔标记（可读性）。

---

### User Story 4 - 降级模式（GitHub API 不可用容错）(Priority: P1)

`DegradedModeManager`（单例，`get_degraded_manager()` 获取）管理 GitHub API 不可用时的降级状态。`DegradedModeReason` 枚举降级原因。降级时系统切换到只读/缓存路径，避免阻塞。

**Why this priority**: 降级模式是 GitHub API 容错的核心机制；保证 API 不可用时系统仍能提供降级服务。

**Independent Test**: 触发 GitHub API 不可用，验证 `get_degraded_manager()` 进入降级模式；API 恢复后验证退出。

**Acceptance Scenarios**:

1. **Given** GitHub API 不可用，**When** `DegradedModeManager` 检测，**Then** 进入降级模式（`DegradedModeReason` 标注原因）。
2. **Given** 降级模式，**When** 消费方查询 `get_degraded_manager()`，**Then** 返回单例（全局一致状态）。
3. **Given** API 恢复，**When** manager 退出降级，**Then** 切回正常路径。

---

### User Story 5 - 方法级 trace 装饰器 (Priority: P1)

`trace_method` 装饰器为方法提供执行 trace（耗时、输入输出摘要）。可配置 `set_trace_min_ms`（最小耗时阈值，低于不记录）与 `set_trace_max_lines`（最大行数，避免日志膨胀）。

**Why this priority**: trace 是性能分析与问题定位的手段；阈值与行数限制防止日志爆炸。

**Independent Test**: 用 `@trace_method` 装饰一个方法，配置 `min_ms=100`，调用快速方法验证不记录、调用慢方法验证记录。

**Acceptance Scenarios**:

1. **Given** `@trace_method` 装饰的方法，**When** 调用，**Then** 记录执行 trace（耗时 + 摘要）。
2. **Given** `set_trace_min_ms(100)`，**When** 方法耗时 < 100ms，**Then** 不记录 trace（阈值过滤）。
3. **Given** `set_trace_max_lines(N)`，**When** 输出超过 N 行，**Then** 截断（防止日志膨胀）。

---

### User Story 6 - 公开 API 契约（横切基础设施）(Priority: P1)

observability 经 `__init__.py` 导出横切基础设施符号（日志配置、审计、事件追加、降级、trace 配置）。所有符号 MUST 为合法导出类型（callable / dataclass / Pydantic / 路径辅助函数）。

**Why this priority**: 公开 API 是 observability 作为横切基础设施的契约边界；导出违规会污染全项目。

**Independent Test**: 检查 `__all__` 所有符号类型合法，且与 `_LAZY_IMPORTS`（如有）一致。

**Acceptance Scenarios**:

1. **Given** observability `__all__`，**When** 类型检查，**Then** 所有导出为 callable（setup_logging / append_* / set_trace_*）/ dataclass（AuditEntry）/ Pydantic / 路径辅助（*_log_dir / *_log_path）。
2. **Given** 路径辅助函数（`logs_root` / `*_log_dir` / `*_log_path`），**When** 调用，**Then** 返回兼容 bare-repo + linked-worktree 的路径。

---

### Edge Cases

- **日志保留**：session 销毁后日志保留供事后排查（CLAUDE.md §Context And File Hygiene：session 日志 `.git/vibe3/logs/{session_name}.log` 不随销毁删除）。
- **degraded_mode 单例**：`get_degraded_manager()` 返回全局单例，跨模块共享降级状态。
- **trace 阈值默认值**：`set_trace_min_ms` / `set_trace_max_lines` 有默认值，未配置时按默认过滤。
- **AuditLogger 内存聚合**：`_entries` 为内存列表，不直接持久化；落盘由 `append_*_event` 或治理链消费方负责。
- **AuditEntry 不可变**：审计记录写入后不可篡改（可追溯性要求）。
- **事件日志分类不可混装**：governance/orchestra/supervisor/tick 各自独立目录与文件，不交叉写入。
- **`governance_dry_run_dir`**：governance dry-run 专用目录（PR #3291 dry-run 条件清理的产物落盘位置）。

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `setup_logging()` MUST 初始化 loguru 结构化日志；日志经 `logger.bind(domain=..., action=..., ...)` 绑定领域上下文。
- **FR-002**: `AuditEntry` MUST 为审计记录数据结构（含 actor/action/detail/timestamp）；`AuditLogger` MUST 在内存维护 `_entries: list[AuditEntry]`（聚合），持久化落盘由消费方（`append_*_event`）负责。
- **FR-003**: 事件日志 MUST 按来源分类独立存储：`append_governance_event` / `append_orchestra_event` / `append_supervisor_event` 各写入对应 `*_events_log_path()`。
- **FR-004**: `append_orchestra_run_separator()` MUST 写入分隔标记，分隔连续 orchestra run。
- **FR-005**: 路径辅助函数（`logs_root` / `governance_log_dir` / `orchestra_log_dir` / `supervisor_log_dir` / `tick_log_dir` / `governance_scans_dir` / `governance_dry_run_dir` / `issues_log_dir` 及对应 `*_log_path`）MUST 兼容 bare-repo + linked-worktree（constitution 原则 V）。
- **FR-006**: `DegradedModeManager` MUST 为单例（`get_degraded_manager()` 获取）；`DegradedModeReason` 枚举降级原因；降级时切换只读/缓存路径。
- **FR-007**: `trace_method` 装饰器 MUST 记录方法执行 trace（耗时 + 摘要）；`set_trace_min_ms` 控制最小耗时阈值；`set_trace_max_lines` 控制最大行数。
- **FR-008**: observability 公开 API（`__init__.py` `__all__`）MUST 只导出横切基础设施符号（callable / dataclass / Pydantic / 路径辅助）。
- **FR-009**: session 销毁后其日志（`.git/vibe3/logs/{session_name}.log`）MUST 保留供事后排查（CLAUDE.md §Context And File Hygiene）。
- **FR-010**: observability MUST NOT 承载业务判断逻辑（横切关注点，只提供记录与查询）。
- **FR-011**: `AuditEntry` 写入后 MUST 不可篡改（可追溯性）。
- **FR-012**: 事件日志分类 MUST 独立：governance / orchestra / supervisor / tick 不交叉写入。
- **FR-013**: 005 的 4 层证据模型流转 MUST 经 `AuditLogger` / 对应 append 函数落盘（005 消费 009 基础设施）。
- **FR-014**: `degraded_mode` MUST 保证跨模块状态一致（单例），避免部分模块降级、部分未降级的不一致。

### Key Entities *(include if feature involves data)*

- **AuditEntry / AuditLogger**：审计记录数据结构与写入器。
- **DegradedModeManager / DegradedModeReason**：降级模式单例管理器 + 原因枚举。
- **trace_method**：方法级 trace 装饰器。
- **路径辅助**：logs_root / *_log_dir / *_log_path（governance/orchestra/supervisor/tick/issues/dry_run）。
- **事件追加函数**：append_governance_event / append_orchestra_event / append_orchestra_run_separator / append_supervisor_event。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `logger.bind(domain=..., action=...)` 输出含结构化字段；`setup_logging()` 后日志可用（可测试）。
- **SC-002**: `AuditLogger.log(AuditEntry(...))` 将条目追加到 `_entries`，含完整 actor/action/detail/timestamp；落盘经 `append_*_event`（可测试）。
- **SC-003**: 三类 append 函数分别写入各自 `*_events_log_path()`（分类独立可测试）。
- **SC-004**: `get_degraded_manager()` 返回全局单例；API 不可用时进入降级、恢复时退出（降级模式可测试）。
- **SC-005**: `trace_method` 按 `min_ms` 过滤、按 `max_lines` 截断（阈值与行数可测试）。
- **SC-006**: observability `__all__` 所有导出为合法类型；路径辅助兼容 bare-repo（modularity + constitution 原则 V 可机器验证）。

## Assumptions

- **baseline 范围假设**：本 spec 覆盖结构化日志、审计、分类事件、降级模式、方法 trace、公开 API 契约。**不**覆盖 4 层证据模型的语义（见 005）、日志的具体格式细节、loguru 内部实现。
- **横切关注点假设**：observability 不承载业务判断，只提供记录与查询；业务层（governance/dispatch/role）消费这些基础设施。
- **与 005 边界假设**：005 描述 4 层证据模型**语义**（observation→suggestion→report→decision 的层级关系）；009 描述**记录机制**（AuditLogger 如何落盘、append_* 如何分类）。二者不重叠。
- **单例假设**：`DegradedModeManager` 全局单例，保证跨模块降级状态一致。
- **日志保留假设**：session 日志销毁后保留（CLAUDE.md §Context And File Hygiene）；清理策略由调用方或运维决定，observability 不自动删除。
