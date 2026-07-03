# Feature Specification: Client Layer Baseline

**Feature Branch**: `dev/issue-3299`

**Created**: 2026-07-03

**Status**: Draft (Baseline / Reverse Specification)

**Spec Mode**: 逆向规格化（Reverse Specification）。本 spec 描述 clients 层**当前代码的行为契约**，作为后续变更的行为参照基线。**不设计新功能、不改代码。**

**Input**: User description: "逆向规格化 client-layer 模块的现有行为契约（baseline spec，非新功能设计）"

## Spec Mode 说明

本 spec 是 **baseline 行为契约**，描述"系统现在如何抽象外部系统（Git/GitHub/SQLite/AI/Serena）为可注入的 Protocol 端口与 Client 实现"。真源：

- `src/vibe3/clients/*.py`（42 个模块：git_client / github_client / sqlite_client / ai_client / serena_client / merged_pr_cache / runtime_assets / sync_rules / store_context 等）
- `src/vibe3/clients/protocols/*`（Narrow Port 定义：git / flow / github / pr / backend / role）
- [docs/standards/client-boundaries.md](../../../docs/standards/client-boundaries.md)（边界与 Narrow Port 权威）
- [docs/standards/client-lifecycle-management.md](../../../docs/standards/client-lifecycle-management.md)（生命周期权威）
- [docs/decisions/0002-protocol-based-di.md](../../../docs/decisions/0002-protocol-based-di.md)（Protocol DI 决策）

**冲突处理**：当代码现状与文档不一致时，本 spec 以代码行为为准并显式标注。**范围边界**：本 spec 不承载项目硬规则，仅引用 [CLAUDE.md](../../../CLAUDE.md)、[.claude/rules/modularity-standards.md](../../../.claude/rules/modularity-standards.md)、[.specify/memory/constitution.md](../../memory/constitution.md)。

**关联 spec**：与 [002-dispatch-execution](../002-dispatch-execution/spec.md) 协作——dispatch 通过 `BackendProtocol` 注入 backend；与 [007-analysis-intelligence](../007-analysis-intelligence/spec.md) 协作——analysis 通过 `SerenaClientProtocol` 注入 client；与 [006-handoff-protocol](../006-handoff-protocol/spec.md) 协作——handoff 通过 `GitPathProtocol` 解析路径。

## 核心定位（诚实记录）

clients 层是**外部系统抽象层**（client-lifecycle §Core Principles：三层架构的底层）。职责：封装外部依赖（subprocess / 文件 I/O / 数据库 / HTTP），提供 Protocol 接口供 mock 注入。clients **不能**调用 services（反向依赖禁止，python-standards 依赖方向强制）。

**规模诚实记录**：clients 是全项目最大模块（42 文件 / ~8300 行 / 56 公开导出），按域分类：github(11) / sqlite(9) / git(5) / ai(2) / serena(1) / 缓存与工具类。

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Narrow Port Pattern（窄端口优于宽 Protocol）(Priority: P0)

GitHub 能力拆分为 7 个窄端口（`protocols/github.py`）：`GitHubAuthPort` / `PRReadPort` / `PRWritePort` / `PRDiffPort` / `PRCommentPort` / `IssueReadPort` / `IssueWritePort`。`GitHubClientProtocol` 由这些窄端口合成（多继承）。消费者按需依赖窄端口，不强制依赖整个 `GitHubClient`。

**Why this priority**: Narrow Port 是 client-boundaries 的核心契约；宽 Protocol 会导致消费者耦合全部能力，阻碍 mock 与替换。

**Independent Test**: 构造一个只实现 `PRReadPort` 的 mock，验证消费者（只声明依赖 `PRReadPort`）能被注入并工作。

**Acceptance Scenarios**:

1. **Given** 消费者只需读 PR，**When** 声明依赖 `PRReadPort`（而非 `GitHubClient`），**Then** 可注入只实现该端口的 mock（Narrow Port）。
2. **Given** `GitHubClientProtocol`，**When** 检查继承，**Then** 由 7 个窄端口合成（多继承集合）。
3. **Given** `PRReadPort` / `PRWritePort` 分离，**When** 只读场景，**Then** 消费者不被迫依赖写能力（权限最小化）。
4. **Given** `IssueReadPort` vs `IssueWritePort`，**When** 查询类 service，**Then** 只依赖读端口。

---

### User Story 2 - Constructor Injection with Fallback（生命周期 scope）(Priority: P0)

services/commands 层通过 constructor injection with fallback 注入 client：`def __init__(self, git_client: GitClient | None = None): self.git_client = git_client or GitClient()`。实例创建分三 scope（client-lifecycle §Instance Creation Scopes）：App-level（`server/registry.py`，单次 app 运行）/ Request-level（service 构造器，单请求）/ Local（函数体，单调用）。

**Why this priority**: 注入模式是可测试性与生命周期治理的核心；fallback 保证默认可用，注入保证可 mock。

**Independent Test**: 构造 service 时不传 client，验证 fallback 创建默认 `GitClient()`；传入 mock 验证被使用。

**Acceptance Scenarios**:

1. **Given** service `__init__(self, git_client=None)`，**When** 不传参构造，**Then** fallback 创建 `GitClient()`（默认可用）。
2. **Given** 同一 service，**When** 传入 mock client，**Then** 使用注入的 mock（可测试性）。
3. **Given** App-level scope（`server/registry.py`），**When** app 启动，**Then** client 创建一次，注入多个 services。
4. **Given** Local scope（函数体），**When** 一次性操作，**Then** 直接构造 `GitClient()`（无注入开销）。

---

### User Story 3 - Protocol-based DI（ADR-0002，services 不 import agents）(Priority: P0)

services 层通过 Protocol（如 `BackendProtocol`）依赖 backend 能力，**禁止**直接 import `vibe3.agents.backends.*`（ADR-0002）。`BackendProtocol` 在 `clients/protocols/backend.py` 定义，agents backends 实现 Protocol，services 注入 Protocol 类型。

**Why this priority**: Protocol DI 是依赖倒置的硬约束（ADR-0002）；违反将导致 services → agents 层级违规。

**Independent Test**: grep services 层 import，验证无 `from vibe3.agents.backends` 直接导入（Protocol 隔离）。

**Acceptance Scenarios**:

1. **Given** services 层代码，**When** grep `from vibe3.agents.backends`，**Then** 为零（ADR-0002 强制）。
2. **Given** `BackendProtocol`（`clients/protocols/backend.py`），**When** agents backends 实现它，**Then** services 通过 Protocol 类型注入（依赖倒置）。
3. **Given** `TriggerableRoleDefinitionProtocol`（`clients/protocols/role.py`），**When** roles 层定义角色，**Then** execution 层通过 Protocol 引用角色（不直接 import roles 具体类）。

---

### User Story 4 - Wrapper vs Direct CLI 判断准则 (Priority: P1)

何时用 client wrapper vs 直接 `gh`/`git`（client-boundaries §When to Use）：wrapper 用于响应归一化 / 领域错误处理 / 测试隔离 / 多步编排；直接 CLI 用于简单 pass-through / 原型 / 性能敏感路径。

**Why this priority**: 判断准则是避免过度抽象与遗漏抽象的平衡契约。

**Independent Test**: 检查一个 wrapper（如 `get_pr` → `PRResponse`）含归一化逻辑，验证符合 wrapper 准则；检查一个直接 `gh` 调用为简单 pass-through。

**Acceptance Scenarios**:

1. **Given** 操作需响应归一化（如 `gh` 输出 → `PRResponse` 含 `is_ready`/`ci_passed` 派生字段），**When** 选择，**Then** 用 wrapper（client-boundaries §1）。
2. **Given** 操作需领域错误处理（CLI 错误 → 领域异常），**When** 选择，**Then** 用 wrapper。
3. **Given** 简单 pass-through（无归一化），**When** 选择，**Then** 直接 `gh`/`git`（避免 indirection 成本）。
4. **Given** 多步编排（如 `create_pr` with body repair），**When** 选择，**Then** 用 wrapper（pre/post-condition 编排）。

---

### User Story 5 - Store Context 与 SQLite 初始化 (Priority: P1)

`get_store()`（`store_context.py`）提供 SQLite store 获取入口；`SQLiteClient` 是主 store 客户端；`init_schema`（`sqlite_schema.py`）初始化 schema。`_HasConnection` Protocol 抽象连接持有。SQLite 相关 9 个模块覆盖 schema / migration / query。

**Why this priority**: store 是共享状态真源的物理载体；初始化与获取契约是数据层稳定性的基础。

**Independent Test**: 调用 `get_store()` 获取 store，验证返回已 init schema 的 `SQLiteClient`。

**Acceptance Scenarios**:

1. **Given** `get_store()`，**When** 调用，**Then** 返回已初始化 schema 的 `SQLiteClient`。
2. **Given** `init_schema`，**When** 对新数据库执行，**Then** 创建所有 v3 表（flow_state / flow_issue_links / flow_events / runtime_session 等）。
3. **Given** `_HasConnection` Protocol，**When** 抽象连接持有，**Then** 允许不同 SQLite 连接实现注入。

---

### User Story 6 - Runtime Assets 与 Bare-repo 解析 (Priority: P1)

`runtime_assets`（`runtime_assets_root` / `resolve_runtime_asset` / `resolve_prompt_config` / `bundled_project_root`）解析 vibe3 安装目录的资源。所有路径解析 MUST 兼容 bare-repo + linked-worktree（constitution 原则 V）。

**Why this priority**: runtime assets 是 prompt 配置与运行时资源的寻址基础；bare-repo 兼容是硬约束。

**Independent Test**: 在 bare-repo linked-worktree 中调用 `runtime_assets_root()`，验证从 worktree 自身解析而非仓库根。

**Acceptance Scenarios**:

1. **Given** bare-repo 环境，**When** `runtime_assets_root()` / `resolve_runtime_asset(path)`，**Then** 从 worktree 自身解析（不从仓库根）。
2. **Given** prompt 配置，**When** `resolve_prompt_config()`，**Then** 返回正确的配置路径（兼容 linked-worktree）。
3. **Given** `bundled_project_root()`，**When** 调用，**Then** 返回打包项目根（处理安装路径差异）。

---

### Edge Cases

- **`GitPathProtocol`（`protocols/git.py`）**：路径解析窄端口，被 handoff（006）/ environment（004）/ analysis（007 review_kernel `_repo_root_for_manifest`）等多层消费。
- **`FlowReader` / `FlowStatePort`（`protocols/flow.py`）**：flow 读写窄端口，被 environment（004，`update_flow_metadata`）/ handoff（006）消费。
- **`MergedPRCache` / `RecentPRCache`**：PR 缓存（含 `_ErrorRecorder` Protocol），加速重复查询；缓存失效策略由消费方决定。
- **`sync_rules`（LocalSyncRules / RemoteSyncRules）**：本地/远端同步规则配置，驱动 GitHub 同步策略。
- **`GitClientProtocol` vs `GitPathProtocol`**：前者是完整 git 操作端口（`git_client.py`），后者是窄路径解析端口（`protocols/git.py`），职责分离。
- **`IssueLabelPort`（`github_labels.py`）**：issue label 操作窄端口（governance scan / orchestra 消费）。
- **constructor injection fallback 的默认 client**：`GitClient()` / `GitHubClient()` / `SQLiteClient()` 无参构造必须可用（保证 fallback 路径）。

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: clients 层 MUST 通过 `clients/protocols/` 子目录定义 Narrow Port：git（GitPathProtocol）/ flow（FlowReader, FlowStatePort）/ github（7 窄端口 + 合成的 GitHubClientProtocol）/ pr（BaseResolver）/ backend（BackendProtocol）/ role（TriggerableRoleDefinitionProtocol）。
- **FR-002**: GitHub 能力 MUST 拆分为 7 窄端口（GitHubAuthPort / PRReadPort / PRWritePort / PRDiffPort / PRCommentPort / IssueReadPort / IssueWritePort）；`GitHubClientProtocol` 由这 7 端口合成（多继承）。
- **FR-003**: services/commands 层 MUST 通过 constructor injection with fallback 注入 client：`def __init__(self, client: T | None = None): self.client = client or T()`。
- **FR-004**: 实例创建 MUST 遵循三 scope：App-level（`server/registry.py`）/ Request-level（service 构造器）/ Local（函数体）（client-lifecycle §Scopes）。
- **FR-005**: services 层 MUST NOT 直接 import `vibe3.agents.backends.*`；MUST 通过 `BackendProtocol` 等 Protocol 依赖（ADR-0002）。
- **FR-006**: clients 层 MUST NOT 调用 services 层（依赖方向强制：clients ← services ← server/commands，python-standards）。
- **FR-007**: client wrapper 用于响应归一化 / 领域错误处理 / 测试隔离 / 多步编排；简单 pass-through / 原型 / 性能敏感路径用直接 `gh`/`git`（client-boundaries §When to Use）。
- **FR-008**: `get_store()` MUST 返回已初始化 schema 的 `SQLiteClient`；`init_schema` MUST 创建所有 v3 表。
- **FR-009**: `runtime_assets_root()` / `resolve_runtime_asset()` / `resolve_prompt_config()` / `bundled_project_root()` MUST 兼容 bare-repo + linked-worktree（constitution 原则 V）。
- **FR-010**: 所有 client 公开 API MUST 经 `clients/__init__.py` lazy import 导出；`__all__` 与 `_LAZY_IMPORTS` 严格一致（modularity-standards）。
- **FR-011**: `GitClient`（git 操作）与 `GitPathProtocol`（路径解析窄端口）MUST 职责分离，不混装。
- **FR-012**: `MergedPRCache` / `RecentPRCache` MUST 提供 PR 缓存能力（含 `_ErrorRecorder` Protocol 记录错误）。
- **FR-013**: `sync_rules` MUST 区分 `LocalSyncRules` 与 `RemoteSyncRules`，驱动 GitHub 同步策略。
- **FR-014**: 所有 client 无参构造（`GitClient()` / `GitHubClient()` / `SQLiteClient()`）MUST 可用，保证 constructor injection fallback 路径。

### Key Entities *(include if feature involves data)*

- **Narrow Ports**（`clients/protocols/`）：GitPathProtocol / FlowReader / FlowStatePort / GitHubAuthPort / PRReadPort / PRWritePort / PRDiffPort / PRCommentPort / IssueReadPort / IssueWritePort / BaseResolver / BackendProtocol / TriggerableRoleDefinitionProtocol。
- **核心 Clients**：GitClient / GitHubClient / SQLiteClient / AIClient / AISuggestionClient / SerenaClient。
- **缓存**：MergedPRCache / RecentPRCache（含 _ErrorRecorder Protocol）。
- **资源/配置**：runtime_assets（root/resolve/bundled_project_root）/ sync_rules（LocalSyncRules/RemoteSyncRules）/ store_context（get_store）。
- **GitHubClientProtocol**：7 窄端口合成的宽 Protocol（向后兼容）。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: services 层 grep `from vibe3.agents.backends` 为零（ADR-0002 Protocol DI 可机器验证）。
- **SC-002**: 消费者声明依赖 `PRReadPort`（窄端口）时，可注入只实现该端口的 mock（Narrow Port 可测试）。
- **SC-003**: service 不传 client 构造时 fallback 创建默认 client；传 mock 时使用 mock（constructor injection 可测试）。
- **SC-004**: clients 层 grep `from vibe3.services` / `import vibe3.services` 为零（依赖方向可机器验证）。
- **SC-005**: `get_store()` 返回已 init schema 的 store；`init_schema` 创建所有 v3 表（schema 初始化可测试）。
- **SC-006**: `__all__` 与 `_LAZY_IMPORTS` 键集一致，所有导出为合法类型（modularity 测试可机器验证）。

## Assumptions

- **baseline 范围假设**：本 spec 覆盖 Narrow Port Pattern、constructor injection lifecycle、Protocol-based DI（ADR-0002）、wrapper vs direct 判断、store context、runtime assets。**不**覆盖各 client 内部实现细节（subprocess 调用、HTTP 请求）、具体 SQL 语句（见 SQLite schema）、git 操作语义（见 git client 实现）。
- **三层边界假设**：clients（外部接口）← services（业务编排）← server/commands（请求处理）；依赖方向单向，禁止反向（client-lifecycle §Core Principles，python-standards）。
- **Narrow Port 优于宽 Protocol 假设**：消费者按需依赖窄端口，不强制依赖整个 client（client-boundaries §Narrow Port Pattern）。
- **fallback 默认可用假设**：所有 client 无参构造可用，保证未注入时默认路径工作（client-lifecycle §Allowed Patterns）。
- **bare-repo 兼容假设**：runtime_assets 与路径解析类客户端兼容 bare-repo + linked-worktree（constitution 原则 V，依据 PR #3268 #3253 #3246）。
