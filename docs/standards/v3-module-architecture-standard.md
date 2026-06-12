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
- **单向可见性**：上层模块对下层模块有直接可见性，下层模块对上层模块应保持“盲态”。若需跨层通信，必须通过 `Event Bus` (Domain Event) 或 `Abstract Interfaces`。
- **显式导入优于隐式重导出**：
  - 在核心逻辑模块（如 `execution`, `domain`）中，优先使用 `from vibe3.xxx.yyy import ZZZ`。
  - 避免在 `__init__.py` 中进行大范围的 `import *`。

## 5. 公共接口设计规范 (Public Interface)

- **接口收敛**：
  - 模块应通过 `__init__.py` 显式定义其公开接口。
  - 未在 `__init__.py` 导出的类和函数视为内部实现，不建议跨模块直接调用。
- **内部隐藏**：
  - 仅模块内部使用的子模块或函数，应使用下划线（`_`）前缀。
- **接口命名约定**：
  - Service 结尾：持有状态或负责流程。
  - Client 结尾：负责外部通信。
  - Model 结尾：纯数据结构。

## 6. 模块大小控制 (LOC Governance)

本标准严格继承并执行 [loc-governance.md](loc-governance.md)：

- **理想大小**：单文件 LOC < 300 行。
- **阻断阈值**：单文件 LOC > 400 行将触发 CI 阻断。
- **超限审查**：若必须超过阈值（如核心编排逻辑），需在 `config/v3/loc_limits.yaml` 中登记异常并注明 Reason。
- **职责单一原则 (SRP)**：一个文件（或子模块）仅应有一个变更理由。当 LOC 接近 300 行且包含多个逻辑轴向时，必须进行拆分。

## 7. 与其他标准的关系

- 整体架构愿景：见 [architecture-convergence-standard.md](v3/architecture-convergence-standard.md)
- 详细 LOC 限制：见 [loc-governance.md](loc-governance.md)
- 术语定义：见 [glossary.md](glossary.md)

## 8. services/ 子包边界约束 (Sub-Package Boundaries)

`services/` 包含 9 个子包，每个子包有明确的职责边界和依赖规则。这些约束由 `tests/vibe3/test_modularity/test_services_subpackage_boundaries.py` 自动强制执行。

### 8.1 子包职责与依赖规则

| 子包 | 职责 | 可导入自 | 禁止导入自 |
| :--- | :--- | :--- | :--- |
| `shared/` | 跨领域公共能力（branches, labels, paths, roles, timeline, status_query） | `services/protocols`, L4-L6 模块 | `services/flow`, `services/pr`, `services/issue`, `services/task`, `services/orchestra`（9 个已知违规作为技术债务追踪） |
| `protocols/` | 协议/接口定义（依赖倒置） | 仅 L4-L6 模块 | 所有 `services/` 实现子包 |
| `flow/` | Flow 状态机、生命周期、重建、恢复、投影 | `issue`, `pr`, `task`, `shared`, `protocols` | 不得形成新的双向耦合（超出 4 个已知循环） |
| `pr/` | PR 操作、解析器 | `flow`, `issue`, `task`, `shared`, `protocols` | 不得引入新的耦合 |
| `issue/` | Issue 处理、分支解析、分发策略、标题缓存 | `flow`, `shared`, `protocols` | 不得引入新的耦合 |
| `task/` | Task 管理 | `flow`, `issue`, `pr`, `shared`, `protocols` | 不得引入新的耦合 |
| `orchestra/` | 编排辅助工具 | `shared`, `protocols` | 不得导入业务子包 |
| `handoff/` | Handoff 解析、状态、存储、验证 | `shared`, `protocols` | 不得导入业务子包 |
| `check/` | 代码质量检查（cleanup, lock, PR service, remote） | `shared`, `protocols` | 不得导入业务子包 |

### 8.2 业务子包依赖图

业务子包（`flow`, `pr`, `issue`, `task`）之间的依赖关系如下：

```
flow   → issue, pr, task
pr     → flow, issue, task
issue  → flow
task   → flow, issue, pr
```

### 8.3 已知双向耦合

以下 4 对子包存在双向导入（均为已知技术债务，需逐步消除）：

- `flow` ↔ `pr`
- `flow` ↔ `issue`
- `flow` ↔ `task`
- `pr` ↔ `task`

这些循环在 `KNOWN_SUBPACKAGE_CYCLES` 中注册，由 `test_no_subpackage_bidirectional_coupling` 追踪。新增的双向耦合将触发测试失败。

### 8.4 已知 shared/ 边界违规

`shared/` 当前存在 10 个违规导入业务子包的实例，作为技术债务在 `KNOWN_SHARED_VIOLATIONS` 中注册：

| 文件 | 违规导入 |
| :--- | :--- |
| `shared/branches.py` | `vibe3.services.pr.resolver`, `vibe3.services.flow.service` |
| `shared/labels.py` | `vibe3.services.issue.dispatch_policy` |
| `shared/roles.py` | `vibe3.services.issue.failure` |
| `shared/timeline.py` | `vibe3.services.flow.timeline` |
| `shared/status_query.py` | `vibe3.services.issue.collection`, `vibe3.services.issue.dispatch_policy`, `vibe3.services.issue.title_cache`, `vibe3.services.pr.service`, `vibe3.services.issue.body` |

这些违规由 `test_shared_no_business_imports` 追踪。新增违规将触发测试失败。

### 8.5 CI 强制执行

本节所有约束由以下机制强制执行：

- **CI 工作流**：`.github/workflows/architecture-check.yml` 在每个 PR 上运行 `tests/vibe3/test_modularity/`，零容忍策略（任何违规阻断 PR 合并）。
- **测试套件**：`tests/vibe3/test_modularity/test_services_subpackage_boundaries.py` 提供具体的边界检查。
- **依赖方向测试**：`tests/vibe3/test_modularity/test_dependency_direction.py` 确保无向上导入（跨 6 层模型）。

### 8.6 未覆盖子包说明

`orchestra/`, `handoff/`, `check/` 三个子包的边界规则未在 `test_services_subpackage_boundaries.py` 的依赖图构建器中覆盖，但其约束由以下测试强制：

- `test_shared_no_business_imports`：确保 `shared/` 不导入这些子包
- `test_protocols_no_implementation_imports`：确保 `protocols/` 不导入这些子包
- `test_no_upward_imports`：确保这些子包不违反分层规则

本节文档准确描述其边界，CI 强制执行由上述测试间接保证。
