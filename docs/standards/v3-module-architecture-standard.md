# V3 模块架构标准 (V3 Module Architecture Standard)

状态：Active
日期：2026-05-23

## 1. 目的

本标准定义 Vibe 3.0 的子模块结构与职责边界，旨在：
- 防止循环依赖（Circular Dependencies）。
- 减少代码冗余，统一横向能力入口。
- 确保清晰的分层架构，降低认知负担。
- 为后续的自动化治理提供结构化参考。

## 2. 分层架构规则 (3-Tier & 6-Layer Mapping)

Vibe 3.0 采用 **3-Tier 战略分层** 模型作为顶层职责划分，并辅以 **6-Layer 实现分层** 进行代码约束。

### 2.1 3-Tier 战略分层 (Architecture Tiers)

| 层级 (Tier) | 名称 | 职责 (Responsibility) | 对应六层模型 | 关联执行等级 |
| :--- | :--- | :--- | :--- | :--- |
| **Tier 3** | **Cognitive / Governance** | 认知与治理：负责全局策略、规则、Supervisor 治理、Issue 分检 (Intake) 与池化 (Pool)、Roadmap 规划。 | Layer 1, 2, 3 (part) | L1, L2 |
| **Tier 2** | **Skill Layer** | 技能/编排层：负责 Flow 状态机、任务编排、Agent 执行 (Plan/Run/Review)。 | Layer 3, 4 | L3 |
| **Tier 1** | **Shell Layer** | 壳层/原子能力：提供原子指令、环境原语、基础设施。 | Layer 2, 5, 6 | L3, L4 |

**注意**：Architecture Tier 定义的是**职责边界**，而 Runtime Execution Level (L1-L4) 定义的是**运行隔离级别**。两者在逻辑上是正交的。

---

### 2.2 六层实现分层 (Implementation Layers)

层级编号约定：Layer 1 为最上层（交互入口），Layer 6 为最底层（基础设施）。依赖方向始终向下（Layer N 仅可依赖 Layer ≥ N），下层对上层保持盲态。

1. **CLI 层** (`cli.py`, `__main__.py`)
   - **职责**：命令行主入口。负责顶级 Typer 组装与全局上下文初始化。
   - **规则**：仅做转发，不持有业务逻辑。

2. **Command & IO Gateway 层** (`commands/`, `server/`, `ui/`)
   - **Commands**：原子 CLI 命令逻辑。将用户动作转化为业务请求。
   - **Server**：HTTP/Webhook/MCP 服务入口。
   - **UI**：控制台输出原语。
   - **规则**：作为外部世界（人类/HTTP/终端）与编排核心之间的网关。

3. **Orchestration Core 层** (`domain/`, `services/`, `shared/`, `orchestra/`, `runtime/`, `execution/`, `roles/`)
   - **Domain**：事件驱动的业务编排真源。定义领域事件、状态机转换。
   - **Services**：具体的业务功能逻辑。
   - **Shared**：跨领域公共能力承载层（labels, paths, errors）。
   - **Orchestra**：顶层调度外壳。
   - **Runtime**：运行时内核（心跳循环、分发器）。
   - **Execution**：执行控制面（并发、Session）。
   - **Roles**：角色行为（Manager, Plan, Run, Review, Supervisor）。
   - **规则**：决定“做什么”并协调“何时执行”。这 7 个模块构成一个**强连通分量 (SCC)**。

4. **Execution Primitives 层** (`agents/`, `prompts/`)
   - **Agents**：Agent 执行引擎驱动。
   - **Prompts**：提示词工厂。
   - **规则**：无状态执行原语。

5. **Environment & Analysis 层** (`environment/`, `analysis/`)
   - **Environment**：物理环境原语（Worktree, Tmux）。
   - **Analysis**：架构洞察工具。

6. **Infrastructure & Models 层** (`adapters/`, `clients/`, `config/`, `exceptions/`, `observability/`, `utils/`, `models/`)
   - **Models**：类型真源（Entities/DTOs）。
   - **Infrastructure**：底层系统服务（日志、配置、数据库客户端）。
   - **规则**：全系统的基石，严禁向上依赖。
   - **内部依赖约束**：L6 内部模块之间不应直接导入。如需跨模块协作，通过依赖注入（DI）解耦。
     - `config` 不得导入 `adapters`（通过 `adapter_resolver` DI 参数注入）
     - `adapters` 不得导入 `clients`（构建逻辑集中在 `adapters/__init__.py`）


### 2.2 水平分类法 (Horizontal Taxonomy within L3)

L3 编排核心内的 6 个模块按职责分为以下水平类别：

| 类别 | 模块 | 职责 | 依赖方向 |
| :--- | :--- | :--- | :--- |
| **Kernel** | `runtime`, `orchestra` | 心跳循环、服务生命周期、编排调度 | 仅依赖自身和 L4–L6 |
| **Command Adapter** | `execution`, `services` | 将业务意图翻译为后端命令 | 可依赖 Kernel 和同类别 |
| **Policy** | `roles` | 声明式角色定义与材料加载 | 可依赖 Kernel、Command Adapter |
| **Plugin Surface** | （保留，暂无模块） | 扩展点占位 | 可依赖 Kernel、Adapter、Policy |
| **Observation** | `domain` | 事件核心、观察门面、状态机 | 可依赖所有类别 |

规则：低编号类别为基石，高编号类别可依赖低编号类别。Kernel 严禁依赖 Adapter/Policy/Plugin/Observation 的内部实现。

Kernel 启动时允许加载的模块（与 #2161 对齐）：`runtime`, `orchestra`, `clients`, `config`, `models`, `observability`, `server`, `utils`, `environment`, `exceptions`。

详细定义见 `src/vibe3/runtime/taxonomy.py`，测试见 `tests/vibe3/test_modularity/test_taxonomy.py`。


## 3. 模块职责边界 (22 Submodules)

Vibe 3.0 核心包 `src/vibe3` 由以下 22 个核心子模块构成：

| 模块 (Module) | 归属层级 | 核心职责 (Primary Responsibility) |
| :--- | :--- | :--- |
| `adapters` | L6 Infrastructure | 适配器注册表，负责不同发行版（如 Vibe Center, Kiro）的兼容性适配。 |
| `agents` | L4 Execution Primitives | Agent 执行引擎。包含后端驱动（Claude/Codex 等）与执行流水线。 |
| `analysis` | L5 Analysis | 架构洞察工具。负责代码依赖扫描、风险审计与治理分析；仅依赖 L6，无状态。 |
| `cli.py` | L1 CLI | 命令行主入口。负责顶级 Typer 组装与全局上下文初始化。 |
| `clients` | L6 Infrastructure | 外部系统客户端封装。如 Git、GitHub、SQLite 等通信适配。 |
| `commands` | L2 Gateway | CLI 命令具体实现。如 `flow`, `task`, `check`, `handoff` 等。 |
| `config` | L6 Infrastructure | 统一配置管理。负责 YAML 加载、校验、默认值注入与动态重载。 |
| `domain` | L3 Orchestration Core | 业务真相真源。持有事件定义（Events）与核心业务编排处理器。 |
| `environment` | L5 Environment | 物理环境抽象。负责 Worktree 分配、隔离与 Tmux 会话探活。 |
| `exceptions` | L6 Infrastructure | 异常体系结构。定义全系统统一的错误码与异常分类。 |
| `execution` | L3 Orchestration Core | 执行中控台。负责并发控制、Session 登记、执行生命周期审计。 |
| `__main__.py` | L1 CLI | Python 模块执行入口。支持 `python -m vibe3` 调用。 |
| `models` | L6 Models | 数据契约。定义 DTO、ORM 映射、API Schema 与状态常量。 |
| `observability` | L6 Infrastructure | 观测系统。负责结构化日志记录、调用链追踪（Trace）与性能监控。 |
| `orchestra` | L3 Orchestration Core | 顶层调度外壳。基于心跳驱动的多角色派发与自动治理逻辑。 |
| `prompts` | L4 Execution Primitives | 提示词工厂。负责模板管理、上下文裁剪与 Agent 指令生成。 |
| `roles` | L3 Orchestration Core | 角色行为定义。包含 Plan, Run, Review, Supervisor 等角色的专属逻辑。 |
| `runtime` | L3 Orchestration Core | 运行时内核。负责心跳循环、异步任务分发、事件总线与路由。 |
| `server` | L2 Gateway | 服务入口。负责 HTTP/Webhook Server 启停与 Driver 装配。 |
| `services` | L3 Orchestration Core | 核心业务逻辑封装。包含 `issue`, `pr`, `task`, `handoff`, `shared` 等核心业务域的拆分实现。 |
| `shared` | L3 Orchestration Core | 跨领域公共能力承载层。负责 labels, paths, errors, branches 等通用逻辑。 |
| `ui` | L2 Gateway | 展示原语。负责控制台 UI 组件、时间轴视图、表格格式化与着色。 |
| `utils` | L6 Infrastructure | 系统工具集。提供文件操作、字符串处理、路径解析等通用辅助。 |


## 4. 依赖规则 (Dependency Rules)

- **禁止循环依赖**：严禁 A -> B -> A 的引用链。若出现，必须将共用部分提取至 `models` 或更低层级。
- **单向可见性**：上层模块对下层模块有直接可见性，下层模块对上层模块应保持”盲态”。若需跨层通信，必须通过 `Event Bus` (Domain Event) 或 `Abstract Interfaces`。
- **显式导入优于隐式重导出**：
  - 在核心逻辑模块（如 `execution`, `domain`）中，优先使用 `from vibe3.xxx.yyy import ZZZ`。
  - 避免在 `__init__.py` 中进行大范围的 `import *`。

## 5. Aggregator Import Policy

Package aggregators (barrel modules like `vibe3.services`, `vibe3.exceptions`, `vibe3.config`) use lazy `__getattr__` exports for convenience and backward compatibility. The public API remains the contract: all cross-module imports MUST go through the target package's `__init__` per [modularity-standards.md](../../.claude/rules/modularity-standards.md).

### 5.1 When Barrel Imports Are Appropriate

**Recommended**: High-level orchestration code (L1-L3) that consumes many symbols from a package and benefits from the convenience surface.

Example:
```python
# Good: High-level orchestration importing many services
from vibe3.services import (
    FlowOrchestratorService,
    IssueFlowService,
    TaskOrchestratorService,
)
```

**Rationale**: The `vibe3.services` barrel is explicitly designed as the aggregator for service-layer consumers. It provides a stable convenience surface for orchestration code.

### 5.2 When to Be Cautious

Low-level modules (L6 infrastructure: `clients/`, `utils/`, `adapters/`) should be careful about depending on barrels that re-export from higher layers. This is a **layer discipline** concern, not a type-safety concern:

- An L6 `clients/` module importing from `vibe3.services` barrel creates an upward dependency on L3 orchestration code — this violates layer blindness.
- An L6 module importing exception **types** (defined directly in `exceptions/__init__.py`) from `vibe3.exceptions` is legitimate — exception types are L6 infrastructure.
- An L6 module importing lazy **functions** (like `classify_error_hybrid`) from `vibe3.exceptions` barrel creates a dependency on the lazy-export graph — assess whether this dependency belongs at L6.

**If a low-level module genuinely needs a capability currently accessed through a barrel**: resolve through proper architectural channels — dependency injection, protocol extraction, callback registration, ownership move, or enhancing the typed public API. Never resolve by bypassing the public API with deep imports.

### 5.3 How TYPE_CHECKING Ensures Mypy Safety

The lazy `__getattr__` pattern is paired with `TYPE_CHECKING` blocks to give mypy full type information:

```python
# vibe3/exceptions/__init__.py
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vibe3.exceptions.error_classification import (
        classify_error_hybrid,
        get_error_handling_contract,
    )

_LAZY_IMPORTS = {
    “classify_error_hybrid”: “vibe3.exceptions.error_classification”,
}

def __getattr__(name: str) -> object:
    if name in _LAZY_IMPORTS:
        module = importlib.import_module(_LAZY_IMPORTS[name])
        value = getattr(module, name)
        globals()[name] = value
        return value
    raise AttributeError(...)
```

**How it works**:
- At runtime: `__getattr__` lazily imports and returns the actual function/class.
- At type-check time: mypy sees the `TYPE_CHECKING` block and resolves full type information. The `__getattr__` body is not executed by mypy.

When mypy has proper project context (`uv run mypy src/vibe3`), TYPE_CHECKING blocks provide correct type information for all barrel exports. If mypy returns `Any` for project functions, check `ignore_missing_imports` configuration — files outside the project tree lack the context mypy needs to resolve TYPE_CHECKING imports.

### 5.4 Enforced Import Boundaries

The following boundaries are enforced by automated tests as layer-discipline guards:

1. **`src/vibe3/clients/**` must not import from `vibe3.services` barrel**
   - Enforced by: `test_clients_no_services_import`
   - Rationale: L6 infrastructure must not depend on L3 orchestration barrels.

2. **`src/vibe3/clients/**` imports from `vibe3.exceptions` barrel are tracked**
   - Enforced by: `test_clients_no_exceptions_import`
   - Rationale: L6 clients may legitimately depend on exception types (defined directly in `__init__.py`). Lazy function imports from the barrel are flagged for review. This is a **baseline tracking gate**, not a hard block — increases require justification.

3. **Barrel import baselines are tracked project-wide**
   - `vibe3.exceptions`: Baseline 161 (tracked by `test_barrel_import_tracking.py`)
   - `vibe3.config`: Baseline 140 (tracked by `test_barrel_import_tracking.py`)
   - Rationale: Risk/trend observation. Increases trigger xfail warnings and require justification. This is NOT a migration plan to replace barrel imports with deep imports.

Violations of rule #1 cause immediate test failure.
Increases in baselines #2 and #3 trigger xfail warnings and require justification.

### 5.5 Resolving Import Boundary Issues Correctly

When a module's dependency on a barrel creates a genuine architectural problem (upward dependency, import cycle risk, excessive coupling), resolve through:

1. **Dependency Injection**: Pass the capability as a parameter rather than importing it.
2. **Protocol Extraction**: Define a `Protocol` in a shared low-level module; the barrel re-exports implement it.
3. **Callback Registration**: Register handlers at startup rather than importing them at call sites.
4. **Ownership Move**: Move the needed symbol to a lower-level module that both sides can legitimately depend on.
5. **Enhance Typed Public API**: Add missing TYPE_CHECKING imports or `.pyi` stubs if type information is incomplete.

**Never** resolve by replacing a barrel import with a deep import (`from vibe3.xxx.yyy import ZZZ`) — this violates [modularity-standards.md](../../.claude/rules/modularity-standards.md) and breaks the public API contract.

## 6. 公共接口设计规范 (Public Interface)

- **接口收敛**：
  - 模块应通过 `__init__.py` 显式定义其公开接口。
  - 未在 `__init__.py` 导出的类和函数视为内部实现，不建议跨模块直接调用。
- **内部隐藏**：
  - 仅模块内部使用的子模块或函数，应使用下划线（`_`）前缀。
- **接口命名约定**：
  - Service 结尾：持有状态或负责流程。
  - Client 结尾：负责外部通信。
  - Model 结尾：纯数据结构。

## 7. 模块大小控制 (LOC Governance)

本标准严格继承并执行 [loc-governance.md](loc-governance.md)：

- **理想大小**：单文件 LOC < 300 行。
- **阻断阈值**：单文件 LOC > 400 行将触发 CI 阻断。
- **超限审查**：若必须超过阈值（如核心编排逻辑），需在 `config/v3/loc_limits.yaml` 中登记异常并注明 Reason。
- **职责单一原则 (SRP)**：一个文件（或子模块）仅应有一个变更理由。当 LOC 接近 300 行且包含多个逻辑轴向时，必须进行拆分。

## 8. 与其他标准的关系

- 整体架构愿景：见 [architecture-convergence-standard.md](v3/architecture-convergence-standard.md)
- 详细 LOC 限制：见 [loc-governance.md](loc-governance.md)
- 术语定义：见 [glossary.md](glossary.md)
