# Feature Specification: Exception Model Baseline

**Feature Branch**: `dev/issue-3299`

**Created**: 2026-07-03

**Status**: Draft (Baseline / Reverse Specification)

**Spec Mode**: 逆向规格化（Reverse Specification）。本 spec 描述 exceptions 子系统**当前代码的行为契约**，作为后续变更的行为参照基线。**不设计新功能、不改代码。**

**Input**: User description: "逆向规格化 exception-model 模块的现有行为契约（baseline spec，非新功能设计）"

## Spec Mode 说明

本 spec 是 **baseline 行为契约**，描述"系统现在如何分类、严重度评级与处理错误"。真源：

- `src/vibe3/exceptions/*.py`（7 模块：error_classification / error_severity / error_codes / runtime_errors / git_error_patterns / diagnostics）
- [docs/standards/error-handling.md](../../../docs/standards/error-handling.md)（三分类权威）
- [docs/standards/v3/error-severity-and-blocking-standard.md](../../../docs/standards/v3/error-severity-and-blocking-standard.md)（严重度与阻塞权威）

**冲突处理**：当代码现状与文档不一致时，本 spec 以代码行为为准并显式标注。**范围边界**：本 spec 不承载项目硬规则，仅引用 [CLAUDE.md](../../../CLAUDE.md) §HARD RULES #13（错误处理分类）、[.specify/memory/constitution.md](../../memory/constitution.md)。

**关联 spec**：与 [001-flow-lifecycle](../001-flow-lifecycle/spec.md) 协作——ErrorSeverity 只影响 FailedGate，**不影响 flow block**（001 的 ERROR vs BLOCK 正交）；与 [002-dispatch-execution](../002-dispatch-execution/spec.md) 协作——FailedGate 消费 ErrorSeverity（CRITICAL/ERROR/WARNING）；与 [008-client-layer](../008-client-layer/spec.md) 协作——`git_error_patterns` 将 git client 错误归类。

## 核心定位（诚实记录）

exceptions 定义**错误分类 taxonomy**（SystemError / UserError / BatchError 三分类）与**严重度评级**（ErrorSeverity: WARNING / ERROR / CRITICAL）。关键澄清（error-handling.md §术语说明）：

- 本 spec 的 `Tier 1/2/3` 指**错误分类层级**（SystemError / UserError / BatchError）
- 与 [glossary.md](../../../docs/standards/glossary.md) §3 的**架构分层**（Tier 1 Shell / Tier 2 Skill / Tier 3 Cognitive）是**不同维度**，独立存在，不应混淆

错误处理分类的治理真源在 [CLAUDE.md](../../../CLAUDE.md) §HARD RULES #13 与 [error-handling.md](../../../docs/standards/error-handling.md)，本 spec 引用不复述。

## User Scenarios & Testing *(mandatory)*

### User Story 1 - SystemError（系统错误，fail-fast）(Priority: P0)

`SystemError` 表示系统基础设施故障（依赖缺失/损坏、外部服务故障、配置损坏、编程错误如类型错误/空指针）。处理原则：立即抛出、fail-fast、不捕获不降级、记录完整错误栈、显示清晰错误信息。

**Why this priority**: SystemError 的 fail-fast 是系统正确性的最后防线；静默捕获会导致故障扩散。

**Independent Test**: 构造 Serena 不可用场景，验证 `SystemError` 向上传播不被静默捕获（对比错误模式：返回错误字典）。

**Acceptance Scenarios**:

1. **Given** 外部服务故障（如 GitHub API 失败），**When** 触发，**Then** 抛 `SystemError`，fail-fast 不降级。
2. **Given** 依赖缺失（如 Serena 不可用），**When** 调用，**Then** `SystemError` 向上传播，不静默返回错误字典。
3. **Given** 编程错误（类型错误/空指针），**When** 发生，**Then** 抛 `SystemError`，记录完整错误栈到日志。

---

### User Story 2 - UserError（业务错误，`-y` 绕过）(Priority: P0)

`UserError` 表示用户操作不符规范但系统正常（输入格式错误、业务规则校验失败、可选步骤失败）。处理原则：提供 `-y` 绕过选项、向用户解释原因、不中断系统。

**Why this priority**: UserError 的绕过机制是人机协作的核心；避免业务校验阻塞自动化流程。

**Independent Test**: 构造 commit message 缺前缀场景，验证抛 `UserError` 含绕过提示；传 `-y` 验证绕过。

**Acceptance Scenarios**:

1. **Given** 输入格式不符（如 commit message 缺前缀），**When** 校验，**Then** 抛 `UserError`，提示 `-y` 绕过。
2. **Given** `UserError` + 用户传 `-y`/`--yes`，**When** 执行，**Then** 绕过校验继续。
3. **Given** 可选步骤失败（如 AST 分析），**When** 触发，**Then** 抛 `UserError`（非 SystemError），系统可继续。

---

### User Story 3 - BatchError（批量错误，续跑后报告）(Priority: P0)

`BatchError` 表示批量任务部分失败。处理原则：继续执行剩余任务、收集所有错误、完成后统一报告。

**Why this priority**: BatchError 的续跑机制是批量任务容错的核心；遇错即停会丢失后续任务结果。

**Independent Test**: 对 10 项批量任务（其中 2 项失败），验证续跑到末尾、收集 2 个错误、统一报告。

**Acceptance Scenarios**:

1. **Given** 批量任务 N 项（部分失败），**When** 执行，**Then** 续跑到末尾（遇错不停）。
2. **Given** 批量任务中 K 项失败，**When** 完成，**Then** 收集所有 K 个错误统一报告（BatchError）。
3. **Given** BatchError 报告，**When** 输出，**Then** 含每项失败原因（可追溯）。

---

### User Story 4 - ErrorSeverity（WARNING / ERROR / CRITICAL，只影响 FailedGate）(Priority: P0)

`ErrorSeverity`（WARNING / ERROR / CRITICAL）评级错误严重度。**关键约束**（error_classification.py NOTE）：CRITICAL/ERROR severity **只影响 FailedGate**，**不影响 flow block**（与 001 的 ERROR vs BLOCK 正交呼应）。`ErrorHandlingContract` 封装严重度与处理策略。

**Why this priority**: severity vs block 的正交是防止"错误自动阻塞 flow"的核心契约；混淆会破坏 flow 生命周期。

**Independent Test**: 构造 CRITICAL severity 错误，验证触发 FailedGate 但**不**直接 block flow（block 需独立条件）。

**Acceptance Scenarios**:

1. **Given** 错误评级 CRITICAL，**When** 处理，**Then** 影响 FailedGate（002），但**不**直接 block flow（block 由独立条件触发，见 001）。
2. **Given** 错误评级 ERROR，**When** 处理，**Then** 影响 FailedGate，不影响 flow block（NOTE 明确）。
3. **Given** 错误评级 WARNING，**When** 处理，**Then** 记录但不阻塞（最低严重度）。
4. **Given** `ErrorHandlingContract`，**When** 封装，**Then** 含 severity + 处理策略（fail-fast / bypass / continue）。

---

### User Story 5 - Git 错误模式归类（git_error_patterns）(Priority: P1)

`git_error_patterns` 将 git client 抛出的原始错误（来自 008 GitClient）按模式归类，映射到对应的错误分类（SystemError / UserError）或错误码。这是 008 clients 层错误的"翻译层"。

**Why this priority**: git 错误归类是区分系统故障（如权限拒绝 → SystemError）与用户操作问题（如分支不存在 → UserError）的关键。

**Independent Test**: 输入"permission denied"git 错误，验证归类为 SystemError；输入"branch not found"验证归类为 UserError。

**Acceptance Scenarios**:

1. **Given** git 权限拒绝错误，**When** `git_error_patterns` 归类，**Then** 映射为 `SystemError`（基础设施故障）。
2. **Given** git 分支不存在错误，**When** 归类，**Then** 映射为 `UserError`（用户操作问题）。
3. **Given** 未匹配的 git 错误，**When** 归类，**Then** 走默认分类（fail-open 或保守归类）。

---

### User Story 6 - Runtime 错误与诊断 (Priority: P1)

`runtime_errors.py` 定义 runtime 层具体错误：`RuntimeInfrastructureError` / `APIError` / `ModelError`。`error_codes.py` 提供错误码枚举（稳定标识）。`diagnostics.py` 提供诊断辅助（错误上下文收集）。

**Why this priority**: runtime 错误细分与错误码是精确定位故障的基础；诊断辅助提升可调试性。

**Independent Test**: 触发 API 故障验证抛 `APIError`；触发模型错误验证抛 `ModelError`；检查错误码稳定性。

**Acceptance Scenarios**:

1. **Given** runtime 基础设施故障，**When** 触发，**Then** 抛 `RuntimeInfrastructureError`（继承 SystemError 族）。
2. **Given** API 调用失败，**When** 触发，**Then** 抛 `APIError`（含 API 上下文）。
3. **Given** 模型调用失败，**When** 触发，**Then** 抛 `ModelError`（含模型上下文）。
4. **Given** `error_codes`，**When** 引用，**Then** 错误码稳定不变（跨版本标识）。

---

### Edge Cases

- **Tier 术语双义**：本 spec 的 `Tier 1/2/3`（错误分类）≠ glossary.md §3 的架构分层 `Tier 1/2/3`（Shell/Skill/Cognitive）——不同维度，error-handling.md §术语说明明确澄清。
- **静默失败反模式**：捕获 SystemError 后返回错误字典属契约违反（error-handling.md §Tier 1 反例）。
- **severity 不 block**：CRITICAL/ERROR 只影响 FailedGate，block flow 需独立条件（与 001 ERROR vs BLOCK 正交一致）。
- **UserError 的 `-y` 不覆盖高风险**：绕过只适用于低风险业务校验，不覆盖 fail-fast / 范围判断 / 多方案选择（见 patterns.md Auto Confirmation Convention）。
- **git_error_patterns 默认分类**：未匹配模式走默认（保守归类或 fail-open）。
- **错误码稳定性**：`error_codes` 一旦发布不应变更标识（跨版本兼容）。

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: 系统 MUST 提供三错误分类：`SystemError`（系统故障，fail-fast）/ `UserError`（业务错误，`-y` 绕过）/ `BatchError`（批量部分失败，续跑后报告）（CLAUDE.md §HARD RULES #13，error-handling.md §一）。
- **FR-002**: `SystemError` MUST 立即抛出、不捕获不降级、记录完整错误栈；静默捕获返回错误字典属契约违反。
- **FR-003**: `UserError` MUST 支持 `-y`/`--yes` 绕过选项；绕过仅适用低风险业务校验，不覆盖高风险决策（patterns.md Auto Confirmation Convention）。
- **FR-004**: `BatchError` MUST 续跑到批量末尾（遇错不停）、收集所有错误、完成后统一报告。
- **FR-005**: `ErrorSeverity`（WARNING / ERROR / CRITICAL）MUST 评级错误严重度；CRITICAL/ERROR **只影响 FailedGate**，**不影响 flow block**（与 001 ERROR vs BLOCK 正交）。
- **FR-006**: `ErrorHandlingContract` MUST 封装 severity + 处理策略（fail-fast / bypass / continue）。
- **FR-007**: `git_error_patterns` MUST 将 git client 原始错误（来自 008）按模式归类到 SystemError / UserError 或对应错误码；未匹配走默认分类。
- **FR-008**: `runtime_errors` MUST 定义 runtime 层具体错误：`RuntimeInfrastructureError` / `APIError` / `ModelError`。
- **FR-009**: `error_codes` MUST 提供稳定错误码枚举（跨版本标识不变）。
- **FR-010**: `diagnostics` MUST 提供错误上下文收集辅助（可调试性）。
- **FR-011**: 错误分类的 `Tier 1/2/3`（SystemError/UserError/BatchError）MUST NOT 与 glossary.md §3 架构分层 `Tier 1/2/3`（Shell/Skill/Cognitive）混淆（不同维度，error-handling.md §术语说明）。
- **FR-012**: 所有层（clients / services / execution / domain）MUST 使用本模块定义的错误类型，不自行发明异常层级。
- **FR-013**: `UserError` 的 `-y` 绕过 MUST NOT 跳过 fail-fast 前置条件或 SystemError（patterns.md：前置条件不满足仍须停止）。
- **FR-014**: 错误处理 MUST 遵循分类原则：SystemError 不降级、UserError 可绕过、BatchError 续跑（三者不可混用处理策略）。

### Key Entities *(include if feature involves data)*

- **SystemError / UserError / BatchError**：三错误分类（Tier 1/2/3 错误分类层级）。
- **ErrorSeverity**：严重度枚举（WARNING / ERROR / CRITICAL）。
- **ErrorHandlingContract**：错误处理契约（severity + 策略）。
- **RuntimeInfrastructureError / APIError / ModelError**：runtime 层具体错误。
- **error_codes**：稳定错误码枚举。
- **git_error_patterns**：git 错误模式归类（008 → 010 翻译层）。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `SystemError` 触发时向上传播不被静默捕获（fail-fast 可测试；对比反例"返回错误字典"被拒绝）。
- **SC-002**: `UserError` + `-y` 绕过成功；不传 `-y` 时中断并提示（绕过机制可测试）。
- **SC-003**: `BatchError` 对含失败的批量任务续跑到末尾、收集所有错误、统一报告（续跑可测试）。
- **SC-004**: CRITICAL/ERROR severity 触发 FailedGate 但**不**直接 block flow（severity vs block 正交可测试，与 001 SC 联合验证）。
- **SC-005**: `git_error_patterns` 对"permission denied"→SystemError、"branch not found"→UserError 正确归类（归类可测试）。
- **SC-006**: grep 全代码库无自行发明的异常层级（统一使用 exceptions 模块，FR-012 可机器验证）。

## Assumptions

- **baseline 范围假设**：本 spec 覆盖三错误分类、ErrorSeverity、ErrorHandlingContract、git_error_patterns、runtime_errors、error_codes、diagnostics。**不**覆盖 FailedGate 内部逻辑（见 002）、flow block 条件（见 001）、各业务层具体错误场景。
- **Tier 术语假设**：错误分类 `Tier 1/2/3`（SystemError/UserError/BatchError）与架构分层 `Tier 1/2/3`（Shell/Skill/Cognitive）是不同维度，本 spec 仅指前者（error-handling.md §术语说明）。
- **severity vs block 假设**：ErrorSeverity 只影响 FailedGate，不影响 flow block；二者正交（与 001 FR ERROR vs BLOCK 一致）。
- **绕过边界假设**：`-y` 绕过只适用低风险业务校验，不覆盖高风险决策/fail-fast/范围判断/多方案选择（patterns.md Auto Confirmation Convention）。
- **错误码稳定假设**：`error_codes` 发布后标识不变，跨版本兼容；新增错误码用新值，不复用旧值。
