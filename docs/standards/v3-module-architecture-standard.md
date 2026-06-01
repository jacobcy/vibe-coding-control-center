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

Vibe 3.0 采用 3-tier 架构模型作为顶层战略划分，并辅以六层架构进行代码实现约束。依赖方向应始终向下（Top-Down）。

### 3-Tier 战略划分

| 层级 (Tier) | 名称 | 职责 (Responsibility) | 对应六层模型层级 |
| :--- | :--- | :--- | :--- |
| **Tier 3** | **Cognitive / Governance** | 认知与治理：负责全局策略、规则、Supervisor 治理。 | Layer 1, 2, 3 (part) |
| **Tier 2** | **Skill Layer** | 技能/编排层：负责 Flow 状态机、任务编排、Agent 执行。 | Layer 2, 3, 4 |
| **Tier 1** | **Shell Layer** | 壳层/原子能力：提供原子指令、环境原语、基础设施。 | Layer 5, 6 |

---

### 六层架构实现标准

1. **CLI & UI 层** (`cli.py`, `ui/`)
   - **职责**：人类与 Agent 的交互入口。负责命令行参数解析、结果美化输出、交互式反馈。
   - **规则**：仅依赖 Command 层或 Models 层，不直接持有业务逻辑。

2. **Command 层** (`commands/`)
   - **职责**：原子 CLI 命令逻辑。负责将用户动作转化为业务请求，进行初步状态校验与现场绑定。
   - **规则**：作为 CLI 与 Service/Domain 之间的桥梁。

3. **Service & Domain 层** (`services/`, `domain/`, `analysis/`)
   - **Domain**：事件驱动的业务编排真源（Authoritative Source）。定义领域事件、状态机转换。
   - **Services**：具体的业务功能逻辑。负责跨模块的业务组合。
   - **Analysis**：专项分析、审计与架构扫描逻辑。
   - **规则**：决定“做什么（What to do）”，不负责具体的“怎么执行（How to execute）”。

4. **Execution 层** (`execution/`, `agents/`, `prompts/`, `roles/`)
   - **职责**：统一执行控制面。负责 Agent 生命周期、容量控制（Capacity）、Session 记账、Prompt 渲染及角色特定材料组装。
   - **规则**：作为 Domain 的执行代理，负责将业务意图转化为物理执行动作。

5. **Environment 层** (`environment/`)
   - **职责**：物理环境原语。负责 Git Worktree 创建/回收、Tmux 会话管理、环境变量隔离。
   - **规则**：仅处理物理资源，不感知业务语义。

6. **Infrastructure & Models 层** (`runtime/`, `config/`, `exceptions/`, `observability/`, `utils/`, `models/`, `adapters/`, `resources/`)
   - **Models**：全系统的类型真源（Entities/DTOs）。
   - **Infrastructure**：底层系统服务。负责配置、心跳、日志、调用链追踪、异常定义、静态资源管理（resources）。
   - **规则**：作为全系统的基石，严禁依赖上述任何上层模块。


## 3. 模块职责边界 (22 Submodules)

Vibe 3.0 核心包 `src/vibe3` 由以下 22 个核心子模块构成：

| 模块 (Module) | 归属层级 | 核心职责 (Primary Responsibility) |
| :--- | :--- | :--- |
| `adapters` | Infrastructure | 适配器注册表，负责不同发行版（如 Vibe Center, Kiro）的兼容性适配。 |
| `agents` | Execution | Agent 执行引擎。包含后端驱动（Claude/Codex 等）与执行流水线。 |
| `analysis` | Service | 架构洞察工具。负责代码依赖扫描、风险审计与治理分析。 |
| `cli.py` | CLI | 命令行主入口。负责顶级 Click 组装与全局上下文初始化。 |
| `commands` | Command | CLI 命令具体实现。如 `flow`, `task`, `check`, `handoff` 等。 |
| `config` | Infrastructure | 统一配置管理。负责 YAML 加载、校验、默认值注入与动态重载。 |
| `domain` | Domain | 业务真相真源。持有事件定义（Events）与核心业务编排处理器。 |
| `environment` | Environment | 物理环境抽象。负责 Worktree 分配、隔离与 Tmux 会话探活。 |
| `exceptions` | Infrastructure | 异常体系结构。定义全系统统一的错误码与异常分类。 |
| `execution` | Execution | 执行中控台。负责并发控制、Session 登记、执行生命周期审计。 |
| `__main__.py` | CLI | Python 模块执行入口。支持 `python -m vibe3` 调用。 |
| `models` | Models | 数据契约。定义 DTO、ORM 映射、API Schema 与状态常量。 |
| `observability` | Infrastructure | 观测系统。负责结构化日志记录、调用链追踪（Trace）与性能监控。 |
| `orchestra` | Runtime | 顶层调度外壳。基于心跳驱动的多角色派发与自动治理逻辑。 |
| `prompts` | Execution | 提示词工厂。负责模板管理、上下文裁剪与 Agent 指令生成. |
| `resources` | Infrastructure | 静态资源管理。负责运行时所需的文件模板、资产与内置素材。 |
| `roles` | Execution | 角色行为定义。包含 Plan, Run, Review, Supervisor 等角色的专属逻辑。 |
| `runtime` | Runtime | 运行时内核。负责心跳循环、异步任务分发、事件总线与路由。 |
| `server` | Server | 服务入口。负责 HTTP/Webhook Server 启停与 Driver 装配。 |
| `services` | Service | 业务逻辑封装。如 `TaskService`, `FlowService`, `AuditService` 等。 |
| `ui` | UI | 展示原语。负责控制台 UI 组件、时间轴视图、表格格式化与着色。 |
| `utils` | Infrastructure | 系统工具集. 提供文件操作、字符串处理、路径解析等通用辅助。 |


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
