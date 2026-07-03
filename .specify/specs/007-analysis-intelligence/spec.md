# Feature Specification: Analysis Intelligence Baseline

**Feature Branch**: `dev/issue-3299`

**Created**: 2026-07-03

**Status**: Draft (Baseline / Reverse Specification)

**Spec Mode**: 逆向规格化（Reverse Specification）。本 spec 描述 analysis 子系统**当前代码的行为契约**，作为后续变更的行为参照基线。**不设计新功能、不改代码。**

**Input**: User description: "逆向规格化 analysis-intelligence 模块的现有行为契约（baseline spec，非新功能设计）"

## Spec Mode 说明

本 spec 是 **baseline 行为契约**，描述"系统现在如何提供代码智能（变更范围、符号引用、结构快照、审查内核分类）"。代码真源：

- `src/vibe3/analysis/*`（12 个模块：change_scope / coverage / git_diff_summary / local_review_report / pre_push_scope / pre_push_test_selector / python_file_inspector / review_kernel / review_observation / structure_service / symbol_reference_service / command_analyzer）
- `src/vibe3/analysis/__init__.py`（公开 API 契约："Public analysis APIs that expose direct, validated evidence"）

**冲突处理**：当代码现状与文档不一致时，本 spec 以代码行为为准并显式标注。**范围边界**：本 spec 不承载项目硬规则，仅引用 [CLAUDE.md](../../../CLAUDE.md)、[docs/standards/v3/python-capability-design.md](../../../docs/standards/v3/python-capability-design.md)（capability layer 原则）、[docs/decisions/0002-protocol-based-di.md](../../../docs/decisions/0002-protocol-based-di.md)（Protocol DI）、[.specify/memory/constitution.md](../../memory/constitution.md)。

**关联 spec**：与 [003-role-protocol](../003-role-protocol/spec.md) 协作——`review_kernel` 提供 `review_floor` 分类（003 FR-011 引用）；与 [002-dispatch-execution](../002-dispatch-execution/spec.md) 协作——analysis 提供 `vibe3 inspect` 的代码证据基座。

**诚实记录**：analysis 模块**无专属标准文档**（`python-capability-design.md` 是 Python CLI 设计原则，非 analysis 专属），行为契约主要从代码公开 API 提取。

## 核心定位

analysis 是 **capability layer**（python-capability-design §1）：暴露稳定、可组合、已验证的代码智能能力，隔离 skill 与底层工具。公开 API（`__init__.py`）只暴露 "direct, validated evidence"，不暴露原始未验证数据。analysis **不是** workflow engine / orchestrator / 业务决策器。

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 变更范围分类（ChangedFileScope）(Priority: P0)

`classify_changed_files()` 将变更文件分类为 `ChangedFileScope`（source_files / test_files / v3_test_files / hook_files）。谓词函数 `is_test_file` / `is_v3_source_file` / `is_v3_test_file` / `is_hook_file` 提供路径判定。这是 `vibe3 inspect base` 的基座。

**Why this priority**: 变更范围分类是所有代码智能分析的入口；分类错误将污染下游审查与测试选择。

**Independent Test**: 给定一组变更文件（含 source/test/hook），调用 `classify_changed_files`，验证分类到对应列表。

**Acceptance Scenarios**:

1. **Given** 变更含 `src/vibe3/x.py`、`tests/vibe3/test_x.py`、`lib/hooks.sh`，**When** `classify_changed_files`，**Then** 分别归入 source_files / v3_test_files / hook_files。
2. **Given** `is_test_file("tests/foo.py")`，**When** 谓词判定，**Then** 返回 True（匹配 test 路径模式）。
3. **Given** `is_v3_source_file("src/vibe3/x.py")` vs `is_v3_source_file("scripts/x.py")`，**When** 判定，**Then** 前者 True、后者 False（v3 source 限定 `src/vibe3/`）。

---

### User Story 2 - Review Kernel 分类（review_floor）(Priority: P0)

`load_review_kernel(manifest_path)` 加载 `ReviewKernelManifest`（含 `ReviewKernelEntry` 列表，每条含 path 模式 + `review_floor: ReviewDepth`）。`classify_review_kernel(manifest, sources)` 对一组变更源文件返回最大 review depth（`_max_depth` 聚合）。`is_architecture_path` 识别架构核心路径。

**Why this priority**: review_kernel 是审查强度的判定引擎，`review_floor` 直接驱动 reviewer 行为（003 FR-011）。

**Independent Test**: 加载一个含 `src/vibe3/runtime/heartbeat.py → repeated` 的 manifest，对含该文件的变更集调用 `classify_review_kernel`，验证返回 `repeated` depth。

**Acceptance Scenarios**:

1. **Given** manifest 含 entry `<runtime/heartbeat.py, review_floor=repeated>`，**When** 变更集含该文件，**Then** `classify_review_kernel` 返回 `repeated`（`_max_depth` 聚合）。
2. **Given** manifest entry path 越界，**When** `load_review_kernel`，**Then** `_validate_entry_path` 拒绝并抛错（路径校验）。
3. **Given** 变更集命中多个 entry，**When** 分类，**Then** 返回这些 entry 中最大的 review_floor（`_max_depth`）。
4. **Given** `is_architecture_path` 判定，**When** 路径属于架构核心，**Then** 返回 True（架构路径识别）。

---

### User Story 3 - 符号引用 Protocol DI（SymbolReferenceProvider）(Priority: P0)

符号引用能力通过 `SymbolReferenceProvider` Protocol（`find_definition` / `find_references`）抽象，`SerenaSymbolReferenceProvider` 是基于 Serena 的实现（注入 `SerenaClientProtocol`）。`ProviderSymbol` 是 provider-neutral 的零偏移符号位置。`inspect_symbol` 是公开入口。

**Why this priority**: Protocol DI 是 analysis 可替换性的核心（ADR-0002）；允许切换 LSP/Serena/其他 provider 而不改动消费者。

**Independent Test**: 注入一个 mock `SerenaClientProtocol`，调用 `SerenaSymbolReferenceProvider.find_references`，验证返回 `ProviderSymbol` 列表。

**Acceptance Scenarios**:

1. **Given** `SymbolReferenceProvider` Protocol，**When** 任何 provider 实现它，**Then** 消费者（`inspect_symbol`）可无改动切换。
2. **Given** `SerenaSymbolReferenceProvider(client)` 注入 client，**When** `find_definition(file, symbol)`，**Then** 返回 `ProviderSymbol | None`（provider-neutral 位置）。
3. **Given** `find_references(file, identity)`，**When** 调用，**Then** 返回 `list[ProviderSymbol]`（所有引用位置）。
4. **Given** `ProviderSymbol`，**When** 检查字段，**Then** 为零偏移（zero-based）符号位置（provider-neutral）。

---

### User Story 4 - AST 结构快照（FileStructure）(Priority: P1)

`structure_service` 基于 `ast` 模块提供 Python/shell 文件结构快照：`analyze_python_file` / `analyze_shell_file` / `analyze_file` 返回 `FileStructure`（含 `FunctionInfo` 列表），`collect_python_file_structures` 批量收集。`StructureError` 是结构错误。

**Why this priority**: 结构快照是 symbol 分析与 LOC 治理的基础数据；无 side effect，可重复执行。

**Independent Test**: 对一个含函数定义的 Python 文件调用 `analyze_python_file`，验证返回 `FileStructure` 含对应 `FunctionInfo`。

**Acceptance Scenarios**:

1. **Given** Python 文件含 `def foo()` 与 `async def bar()`，**When** `analyze_python_file`，**Then** `FileStructure.functions` 含两个 `FunctionInfo`（`ast.FunctionDef` + `ast.AsyncFunctionDef`）。
2. **Given** shell 脚本，**When** `analyze_shell_file`，**Then** 返回对应 `FileStructure`。
3. **Given** 一组 Python 文件，**When** `collect_python_file_structures(root)`，**Then** 批量返回所有 `FileStructure`。
4. **Given** 解析失败（语法错误），**When** `analyze_python_file`，**Then** 抛 `StructureError`（继承 `VibeError`）。

---

### User Story 5 - Pre-push 分析（scope + test selector）(Priority: P1)

`pre_push_scope` 与 `pre_push_test_selector` 提供 pre-push 阶段的变更范围与测试选择分析，驱动"只跑相关测试"策略（HARD RULES #14 本地测试节奏的代码支撑）。

**Why this priority**: pre-push 分析是 CI 优先测试策略的本地支撑，减少全量测试开销。

**Independent Test**: 给定一个变更范围，调用 `pre_push_test_selector`，验证返回相关测试子集（非全量）。

**Acceptance Scenarios**:

1. **Given** 变更范围（来自 `classify_changed_files`），**When** `pre_push_test_selector` 分析，**Then** 返回相关测试子集（基于变更文件映射）。
2. **Given** pre-push scope，**When** `pre_push_scope` 计算，**Then** 输出受影响的测试范围（非全量）。

---

### User Story 6 - 公开 API 只暴露已验证证据 (Priority: P1)

`analysis/__init__.py` 通过 lazy import 只导出"direct, validated evidence"符号（`_LAZY_IMPORTS` 与 `__all__` 严格一致，modularity-standards）。未经验证的中间数据不进入公开 API。

**Why this priority**: 公开 API 契约是 analysis 作为 capability layer 的可信边界；泄漏中间数据会污染消费者。

**Independent Test**: 检查 `__all__` 与 `_LAZY_IMPORTS` 一致，且所有导出符号都是已验证的 evidence 类型（dataclass / Pydantic model / callable）。

**Acceptance Scenarios**:

1. **Given** `analysis/__init__.py`，**When** 检查 `__all__` vs `_LAZY_IMPORTS`，**Then** 二者键集完全一致（modularity-standards 强制）。
2. **Given** 任意导出符号，**When** 类型检查，**Then** 为 callable / dataclass / Pydantic model（不允许裸实例，modularity-standards）。
3. **Given** lazy import，**When** 首次访问符号，**Then** 经 `__getattr__` 动态导入并缓存（避免循环依赖）。

---

### Edge Cases

- **review_kernel manifest 路径校验**：`_validate_entry_path` 拒绝越界 entry path；`_repo_root_for_manifest` 解析 repo root（兼容 bare-repo + linked-worktree，constitution 原则 V）。
- **classify_review_kernel 聚合**：多 entry 命中时取 `_max_depth`（而非首匹配），保证审查强度不降级。
- **ProviderSymbol 零偏移**：provider-neutral，底层 Serena（1-based）与 LSP（0-based）差异由 provider 内部归一化。
- **analyze_python_file 语法错误**：抛 `StructureError`（继承 `VibeError`），不静默吞错。
- **lazy import 缓存**：`globals()[name] = value` 缓存避免重复 import，但需注意 mock patching 时序。
- **command_analyzer**：命令分析模块（从命令提取意图），服务于 `vibe3 inspect` 的命令理解层。

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: analysis 公开 API（`__init__.py`）MUST 只暴露 "direct, validated evidence"，经 lazy import 加载；`__all__` 与 `_LAZY_IMPORTS` MUST 严格一致（modularity-standards）。
- **FR-002**: `classify_changed_files(files)` MUST 将变更文件分类到 `ChangedFileScope`（source_files / test_files / v3_test_files / hook_files）；谓词 `is_test_file` / `is_v3_source_file` / `is_v3_test_file` / `is_hook_file` 提供单文件判定。
- **FR-003**: `load_review_kernel(manifest_path)` MUST 加载 `ReviewKernelManifest`（含 `ReviewKernelEntry` 列表，每条 path 模式 + `review_floor: ReviewDepth`）；`_validate_entry_path` 拒绝越界路径。
- **FR-004**: `classify_review_kernel(manifest, sources)` MUST 对变更源文件集返回最大 review depth（`_max_depth` 聚合，多 entry 命中取最大）；`is_architecture_path` 识别架构核心路径。
- **FR-005**: 符号引用能力 MUST 通过 `SymbolReferenceProvider` Protocol 抽象（`find_definition` / `find_references`）；`SerenaSymbolReferenceProvider` 注入 `SerenaClientProtocol` 实现；`ProviderSymbol` 为 provider-neutral 零偏移位置（ADR-0002）。
- **FR-006**: `inspect_symbol` MUST 为符号引用的公开入口，返回 `SymbolInspectionResult`。
- **FR-007**: `analyze_python_file` / `analyze_shell_file` / `analyze_file` MUST 基于 AST 返回 `FileStructure`（含 `FunctionInfo` 列表）；解析失败抛 `StructureError`（继承 `VibeError`）。
- **FR-008**: `collect_python_file_structures(root)` MUST 批量返回所有 Python 文件的 `FileStructure`。
- **FR-009**: `pre_push_scope` 与 `pre_push_test_selector` MUST 基于 `classify_changed_files` 的范围输出受影响测试子集（非全量）。
- **FR-010**: `get_git_diff_summary` MUST 提供 git diff 摘要（驱动变更范围分析的输入）。
- **FR-011**: `CoverageService` MUST 提供覆盖率能力（服务于测试完整性判断）。
- **FR-012**: `find_latest_prepush_report` / `LocalReviewReport` MUST 提供本地审查报告的定位与表示。
- **FR-013**: `build_review_observation` MUST 构建审查观察（连接 analysis 与 governance 审计链，见 005）。
- **FR-014**: analysis 模块 MUST NOT 承担 workflow 编排或业务决策（python-capability-design §1：只是 capability layer）。

### Key Entities *(include if feature involves data)*

- **ChangedFileScope**：变更文件分类结果（source/test/v3_test/hook lists）。
- **ReviewKernelManifest / ReviewKernelEntry**：审查内核 manifest（path 模式 + review_floor depth）。
- **ReviewDepth**：审查深度枚举（如 repeated），由 003 reviewer 消费。
- **SymbolReferenceProvider / SerenaSymbolReferenceProvider**：符号引用 Protocol + Serena 实现（ADR-0002 DI）。
- **ProviderSymbol**：provider-neutral 零偏移符号位置。
- **FileStructure / FunctionInfo**：AST 结构快照（Pydantic model）。
- **StructureError**：结构错误（继承 VibeError）。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `classify_changed_files` 对混合变更集（source/test/hook）正确分类到对应列表（可测试）。
- **SC-002**: `classify_review_kernel` 对命中 entry 的变更集返回对应 review_floor，多 entry 取 `_max_depth`（可测试）。
- **SC-003**: 注入 mock `SerenaClientProtocol`，`SerenaSymbolReferenceProvider.find_references` 返回 `ProviderSymbol` 列表（Protocol DI 可测试）。
- **SC-004**: `analyze_python_file` 对含函数定义的文件返回正确 `FileStructure`；语法错误抛 `StructureError`（可测试）。
- **SC-005**: `__all__` 与 `_LAZY_IMPORTS` 键集一致，所有导出为 callable/dataclass/Pydantic（modularity 测试可机器验证）。
- **SC-006**: analysis 模块不包含 workflow 编排或业务决策逻辑（capability layer 边界可静态检查）。

## Assumptions

- **baseline 范围假设**：本 spec 覆盖变更范围分类、review_kernel、符号引用 Protocol DI、AST 结构快照、pre-push 分析、公开 API 契约。**不**覆盖 reviewer 如何消费 review_floor（见 003）、`vibe3 inspect` 命令编排（属 commands 层）、Serena client 内部实现（属 clients 层，见 008）。
- **无专属标准假设**：analysis 模块无专属标准文档，行为契约从代码公开 API 提取；`python-capability-design.md` 提供 capability layer 原则（非 analysis 专属）。
- **Protocol DI 假设**：`SymbolReferenceProvider` 遵循 ADR-0002，允许 provider 切换；`ProviderSymbol` 屏蔽底层偏移差异。
- **review_floor 边界假设**：007 描述 review_kernel 的加载与分类机制；003 描述 role 协议层如何引用 review_floor 驱动 reviewer——二者不重叠。
- **AST 无 side effect 假设**：`analyze_*` 函数纯解析，不修改文件、不持久化状态，可重复执行。
