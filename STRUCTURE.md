---
document_type: core-entry
authority:
  - project-structure
  - file-organization
  - docs/decisions/ (Architecture Decision Records - authority for "WHY" decisions)
audience: both
review_frequency: on-change
author: Claude Sonnet 4.5
created: 2024-01-15
last_updated: 2026-06-05
related_docs:
  - SOUL.md
  - CLAUDE.md
  - docs/README.md
---

# Vibe Center 项目结构

本文档定义 Vibe Center 的完整项目结构，说明每个文件和目录的用途。

> **单一事实来源**：本文件是项目结构的权威定义。

## 项目组成

Vibe Center 包含**两个并行实现**：

- **V3 (Python)** - 主要实现，Python 3.12+，路径 `src/vibe3/`
- **V2 (Shell)** - Shell 实现，Zsh，入口 `bin/vibe`

本文档以 **V3 为主视角**进行说明。

### 核心架构 (3-Tier Model)

V3 采用 3-Tier 顶层架构，定义系统的战略职责边界：

- **Tier 3 (Cognitive / Governance Layer)**: 负责全局策略、规则、`supervisor issue` 治理、Issue 分检与 Roadmap 规划。强调基于任务的编排。
- **Tier 2 (Skill Layer)**: 负责 Flow 状态机、任务编排、`assignee issue` 执行 (Plan/Run/Review)。
- **Tier 1 (Shell Layer)**: 提供原子级能力访问、状态读取、环境原语与项目信息检索。

### 执行等级 (Execution Levels)

- **Level 1 (L1 - Inspection)**: 无 Worktree 观察层，负责只读观察与 Metadata 扫描。
- **Level 2 (L2 - Governance)**: 临时隔离治理层，使用临时 Worktree 进行文档治理、测试修补。
- **Level 3 (L3 - Main Development)**: 持久隔离开发层，承载完整的 Plan/Run/Review 生命周期。
- **Level 4 (L4 - Atomic)**: 原子工具层，负责底层原子操作执行。

## 📁 根目录结构

```
vibe-center/
├── STRUCTURE.md                 # 本文件：项目结构定义（你在这里）
├── AGENTS.md                    # AI Agent 入口指南
├── CLAUDE.md                    # 项目上下文、技术栈、硬性规则
├── SOUL.md                      # 项目宪法和核心原则
├── DEVELOPER.md                 # 开发者指南
├── README.md                    # 项目介绍（面向用户）
├── CHANGELOG.md                 # 变更日志
├── VERSION                      # 当前版本号
│
├── .agent/                      # [Group: AI Workspace] Agent 核心配置与工作流
│   └── context/memory/          # [TRACKED] 持久化模式记忆目录；注意：claude-memory MCP 是会话回溯的主工具
├── .claude/                     # [Group: AI Workspace] Claude 专用配置与规则
├── .gemini/                     # [Group: AI Workspace] Gemini 专用配置
├── .codex/                      # [Group: AI Workspace] Codex 专用配置与环境
├── .copilot/                    # [Group: AI Workspace] GitHub Copilot 专用配置
├── .trae/                       # [Group: AI Workspace] Trae 专用配置
├── .kiro/                       # [Group: AI Workspace] Kiro Spec 工作区
├── .serena/                     # [Group: AI Workspace] Serena 治理配置
├── .qoder/                      # [Group: AI Workspace] Qoder 专用配置
├── .codebuddy/                  # [Group: AI Workspace] CodeBuddy 专用配置
├── .opencode/                   # [Group: AI Workspace] OpenCode 专用配置
├── .vibe/                       # [Group: AI Workspace] Vibe 内部运行时缓存 (Legacy)
├── .github/                     # GitHub 配置、工作流与 Issue 模板
│
├── bin/                         # CLI 入口 (vibe, vibe3)
├── src/vibe3/                   # [Active Core] V3 Python 实现核心
├── lib/                         # [Legacy / V2] Shell 核心逻辑
├── lib3/                        # V3 Python 核心包装器与仓库重定向
├── scripts/                     # 自动化脚本、安装脚本与工具
├── supervisor/                  # 治理与监督逻辑 (Apply, Governance, Policies)
│
├── config/                      # 配置文件与策略 (Policies, Prompts)
├── tests/                       # 测试 (vibe2, vibe3, 覆盖率报告)
├── skills/                      # 技能定义 (Canonical Source)
├── docs/                        # 人类文档区 (Standards, PRDs, Specs, Reports)
│   ├── decisions/               # [Authority] ADR 系统 (Architecture Decision Records)
│   ├── directives/              # [V3 Active] 指令集文档 (Executor/Manager/Supervisor)
│   ├── handoff/                 # [V3 Active] 执行交接现场 (Artifacts, Results)
│   ├── publish-directives/      # [V3 Active] 发布指令集 (Post-Review Actions)
│   ├── standards/               # 项目标准与规范
│   └── validation/              # [V3 Active] 验证报告与一致性检查
│
├── debug/                       # 调试信息与临时分析报告
├── openspec/                    # 开放规范集成区
├── temp/                        # [Local Only] 运行时产生的临时目录 (Ignored)
└── .worktrees/                  # [Local Only] Git worktrees 存储目录 (Ignored)
```

## 📄 根目录文件职责

### 核心入口文件

> **单一事实原则**：每个文件有明确的职责边界，详见 [SOUL.md](SOUL.md) §0

| 文件 | 职责 | 受众 | 更新频率 |
|------|------|------|---------|
| **SOUL.md** | 项目宪法和核心原则 | 全员 | 极少 |
| **STRUCTURE.md** | 项目结构定义（本文件） | 人类 + AI | 结构变更时 |
| **AGENTS.md** | AI Agent 入口，指向其他文档 | AI | 很少 |
| **CLAUDE.md** | 项目上下文、技术栈、硬性规则 | AI + 人类 | 规则变更时 |
| **README.md** | 项目介绍（面向用户） | 用户 | 功能变更时 |
| **DEVELOPER.md** | 开发者指南 | 人类 | 开发流程变更时 |

### 文件关系图

```
用户 → README.md
       ↓
开发者 → DEVELOPER.md → STRUCTURE.md
                         ↓
AI Agent → AGENTS.md → SOUL.md (宪法和原则)
                    → CLAUDE.md (上下文和硬规则)
                    → STRUCTURE.md (项目结构)
                    → docs/README.md (文档结构)
                    → .agent/README.md (工作流)
```

**单一事实原则**：详见 [SOUL.md](SOUL.md) §0，每个文件只负责自己的领域，其他内容通过引用链接。

## 🗂️ 目录职责详解

### `bin/` - CLI 入口

**职责**：命令行接口的分发入口

**内容**：
- `vibe` - V2 Shell 入口
- `vibe3` - V3 Python 入口

**规则**：
- 只包含命令入口脚本
- 负责参数解析和命令分发
- 不包含业务逻辑

### `src/vibe3/` - V3 Python 实现（主要）

**职责**：Vibe 的主要实现，Python 3.12+

**规则**：
- 使用 `uv` 进行依赖管理
- 禁止使用 `python`/`pip`，必须用 `uv run`
- 详细标准见 [.claude/rules/python-standards.md](.claude/rules/python-standards.md)

**主要模块**：
- `cli.py` - CLI 主入口（Typer 路由分发）
- `__main__.py` - 进程入口（`vibe3 serve` 启动点）
- `adapters/` - 逻辑适配器与外部集成桥接
- `agents/` - AI Agent 调用层（plan/review/run pipeline + backends）
- `analysis/` - 代码智能（symbol 分析、结构快照、变更范围）
- `clients/` - 外部系统客户端（Git, GitHub, AI, Serena, SQLite）
  - `clients/protocols/` - Protocol 定义层（依赖注入接口，支持 mock 测试和解耦）
- `commands/` - CLI 子命令实现（flow, handoff, pr, task, status, inspect 等）
- `config/` - 配置加载、Profile 管理与 Pydantic schema 验证
- `environment/` - 环境资源管理（Session 和 Worktree 统一抽象层）
- `execution/` - 执行控制平面（统一协调层：coordinator, capacity, lifecycle, gates）
- `exceptions/` - 统一异常层级
- `domain/` - 领域事件与 handlers（events, handlers, orchestration_facade）
  - `domain/protocols/` - 领域协议与抽象接口
- `models/` - 领域数据模型（Flow, Handoff, Task, PR, Verdict 等 Pydantic 模型）
- `observability/` - 日志、链路追踪、审计
- `orchestra/` - 编排中枢（issue 分诊、事件调度）
- `prompts/` - Prompt 模板组装与变量解析
- `roles/` - 角色定义和执行模块（manager, plan, run, review, supervisor, governance）
- `runtime/` - 事件驱动运行时（EventBus, Heartbeat）
- `server/` - HTTP 服务层（webhook, MCP, health check）
- `services/` - 核心业务逻辑（issue, pr, task, handoff, check）
  - `services/flow/` - Flow 状态转换、注册、重建与清理
  - `services/issue/` - Issue 生命流程、标题缓存与失败处理
  - `services/pr/` - PR 创建、评审、质量评分与分析
  - `services/task/` - Task 绑定、状态分类与恢复逻辑
  - `services/handoff/` - Handoff 记录、存储与验证
  - `services/shared/` - 跨领域公共能力（labels, paths, errors, branches）
  - `services/protocols/` - 内部服务协议
- `ui/` - CLI 输出格式化（Rich 渲染）
- `utils/` - 通用工具函数（Git 辅助、分支工具、评论处理等）

**常用命令**：
```bash
uv run python src/vibe3/cli.py <command>  # 运行 CLI
uv run pytest                              # 运行测试
uv run mypy src/vibe3                      # 类型检查
```

**代码分析**：
```bash
vibe3 inspect symbols <file>:<symbol>     # 符号引用分析
vibe3 inspect files <file>                # 文件结构 + 依赖关系
vibe3 inspect commit <sha>                # 改动影响范围
```

#### `clients/protocols/` - Protocol 定义层

**职责**：依赖注入接口定义，支持 mock 测试和架构解耦

**设计原因**：
- **依赖注入**：通过 Protocol 定义接口，允许 services 层依赖抽象而非具体实现
- **可测试性**：方便在测试中注入 mock 对象，隔离外部依赖
- **架构清晰**：明确区分接口契约（clients/protocols/）和具体实现（clients/）
- **向后兼容**：通过 `__init__.py` 重导出，保持所有现有导入路径有效

**模块组成**：
- `backend.py` - Backend 协议（tmux, 执行控制）
- `github.py` - GitHub 客户端协议（PR, Issue, 认证）
- `flow.py` - Flow 读取协议
- `git.py` - Git 路径操作协议
- `pr.py` - PR 创建协议

**导入示例**：
```python
# 推荐：从子模块导入（明确来源）
from vibe3.clients.protocols.github import GitHubClientProtocol

# 兼容：从包根导入（向后兼容）
from vibe3.clients.protocols import GitHubClientProtocol

# 兼容：从旧位置导入（shim 重导出）
from vibe3.services.flow_reader import FlowReader
```

**规则**：
- 只包含 Protocol 定义（`typing.Protocol`）
- 不包含具体实现
- 通过 `__init__.py` 重导出所有公共符号
- 各模块添加 `py.typed` 标记支持类型检查器

### `lib/` - V2 Shell 核心逻辑

**职责**：V2 Shell 实现的业务逻辑

**规则**：
- 单文件 ≤ 300 行
- 总行数 ≤ 7000 行
- 零死代码：所有函数必须有调用方
- 模块化：每个 `.sh` 文件负责一个功能域

**主要模块**：
- `flow.sh` - flow 运行时与 worktree 编排
- `tool.sh` - 工具链管理
- `keys.sh` - API 密钥管理
- `utils.sh` - 通用工具函数

### `lib3/` - V3 Python 核心包装器 (Tier 1 Core Wrapper)

**职责**：V3 Python 核心的运行时包装器，负责仓库重定向和加载密钥。作为 Tier 1 能力的统一入口（hub）。

**规则**：
- 是 V3 Python 运行时的辅助入口。
- 负责 `vibe3` 命令在不同环境下的正确分发。

**主要模块**：
- `vibe.sh` - 核心包装器逻辑。

### `scripts/` - 自动化与辅助脚本

**职责**：存放项目生命周期管理、环境初始化、集成桥接等辅助脚本。

**内容**：
- `init.sh` / `install.sh` - 项目初始化与依赖安装脚本。
- `serena_gate.sh` / `serena_gate.py` - Serena 治理网关。
- `trace_manager.py` - 链路追踪管理工具。
- `openspec_bridge.sh` - OpenSpec 桥接工具。
- `github/` - GitHub 特定集成脚本（如标签同步）。

### `supervisor/` - 治理与监督逻辑

**职责**：定义 AI Agent 的治理策略、监督逻辑与自动治理任务。

**内容**：
- `manager.md` - Vibe Manager 的核心执行指令。
- `apply.md` - 治理 Issue 的自动应用指令。
- `governance/` - 周期性治理扫描策略。
- `policies/` - 细粒度治理策略定义。
- `vibe-*/` - 各种专项治理器（audit, drift, test-runner 等）。

### `config/` - V2 配置文件

**职责**：V2 Shell 实现的配置文件

**子目录**：
- `keys/` - API 密钥配置
- `aliases/` - 命令别名

### `tests/` - 测试

**职责**：存放项目的所有测试代码、测试夹具 (fixtures) 与覆盖率配置。

**子目录**：
- `vibe3/` - **[Active Core]** V3 Python 实现的测试，其子目录结构与 `src/vibe3/` 保持 1:1 镜像对齐。
- `vibe2/` - **[Legacy / V2]** Shell 实现的测试 (Zsh)。
- `conftest.py` - pytest 全局配置与通用 fixtures。
- `test_error_classification.py` - 专项：错误分类逻辑测试。

**规则**：
- V3 测试统一使用 `pytest`。
- 新功能必须包含对应的测试文件。
- 测试覆盖率目标保持在 80% 以上。

### `skills/` - 技能定义

**职责**：技能的 canonical source（权威来源）

**规则**：
- 每个技能一个子目录
- 包含 `SKILL.md` 定义文件
- 运行时通过 symlink 链接到 `.claude/skills/` (Legacy: `.agent/skills/`)

### 🤖 AI Workspace Directories (AI 工作区)

**职责**：存放各种 AI Agent 工具的配置、规则、工作流与临时上下文。

**重要性**：这是 AI 的"办公室"，包含 AI 需要的工具、工作流、模板和上下文 (Rules moved to `.claude/rules/`)

| 目录 | 职责 | 备注 |
|------|------|------|
| `.agent/` | **Agent 核心工作区**。包含模板 (`templates/`)、工作流 (`workflows/`) 和跨任务记忆 (`context/memory/`)。 | Canonical AI workspace |
| `.claude/` | **Claude 专用配置**。存放规则 (`rules/`)、团队模板 (`team-templates/`) 和本地技能运行时。 | 当前主用真源 |
| `.gemini/` | **Gemini 专用配置**。存放 Gemini CLI 的相关指令与钩子。 | Active |
| `.codex/` | **Codex 专用配置**。环境定义与技能映射。 | Active |
| `.kiro/` | **Kiro Spec 工作区**。Spec 定义与设计文档。 | Active |
| `.copilot/` | **GitHub Copilot 专用配置**。 | Supplemental |
| `.trae/` | **Trae 专用配置**。 | Supplemental |
| `.serena/` | **Serena 治理配置**。治理网关与项目元数据。 | Governance |
| `.qoder/` | **Qoder 专用配置**。 | Supplemental |
| `.codebuddy/` | **CodeBuddy 专用配置**。 | Supplemental |
| `.opencode/` | **OpenCode 专用配置**。 | Supplemental |
| `.vibe/` | **Vibe 内部运行时缓存 (Legacy)**。 | 逐步迁移至 .git/vibe3/ |

#### `.agent/context/` - AI 上下文


| 路径 | 职责 | 更新频率 |
|------|------|---------|
| memory/ | **[TRACKED]** 持久化模式记忆目录（用于存放长期模式与规则补丁）；**注意**：`claude-memory` MCP 是跨会话主动回溯（Active Recall）的主工具。 | 仅补充关键模式 |


#### `.agent/templates/` - 文档模板

**职责**：AI 用来生成文档的模板

**重要**：模板是 AI 工具，放在 `.agent/`，不是 `docs/`

| 模板 | 用途 |
|------|------|
| `prd.md` | PRD 文档模板 |
| `tech-spec.md` | Spec 文档模板 |
| `plan.md` | Plan 文档模板 |
| `test.md` | Test 文档模板 |
| `code.md` | Code 文档模板 |
| `audit.md` | Audit 文档模板 |
| `task-readme.md` | Task README 模板 |

#### `.agent/workflows/` - 工作流定义

**职责**：定义各种工作流程

### `.claude/` - Claude AI 配置 (Current Truth)

**职责**：Claude 环境加载入口，包含项目规则与技能运行时。

#### `.claude/rules/` - 编码规则

**职责**：项目的编码标准与真源 (Moved from `.agent/rules/`)

| 文件 | 职责 |
|------|------|
| `coding-standards.md` | 编码标准 |
| `python-standards.md` | Python 编码标准 |
| `patterns.md` | 设计模式 |

#### `.claude/skills/` - 技能运行时

**职责**：技能的运行时环境（symlinks 到 `skills/`）。

**注意**：这是 Claude Desktop 或 IDE 插件加载技能的实际路径。`.agent/skills/` 为旧路径，目前仍保持同步以兼容旧版工具。

### `.git/vibe3/`、`.git/vibe/`、`~/.vibe/` - 数据存储

**职责**：Vibe 系统的数据存储位置

#### 数据存储位置规则

| 路径 | 职责 | 共享范围 | 版本 | 示例内容 |
|------|------|---------|------|---------|
| **`.git/vibe3/`** | **V3 运行时共享真源**（主仓库） | 所有 worktrees 共享 | V3 | `handoff.db`, `handoff/*/` |
| **`.git/vibe/`** | **V2 运行时共享真源**（主仓库） | 所有 worktrees 共享 | V2 | `registry.json`, `worktrees.json`, `tasks/*/` |
| **`~/.vibe/`** | **用户级全局配置** | 当前用户跨仓库共享 | V2/V3 | loader、keys、skills 偏好 |
| **`<worktree>/.vibe/`** | **历史本地缓存方案（已淘汰）** | 仅历史文档背景 | V2 | 不再作为当前运行时真源 |

#### V3 数据存储（`.git/vibe3/`）

**`.git/vibe3/handoff.db`** - SQLite 数据库（跨项目共享）
- 存储所有 flow 状态 and 事件
- 包含 `flow_state` 和 `flow_events` 表
- 所有 worktree 共享访问
- 通过 `git rev-parse --git-common-dir` 定位

**`.git/vibe3/handoff/{branch-safe}/`** - Handoff 数据（跨项目共享）
- `current.md` - 当前 handoff 文件
- `plan-*.md` - Plan 文档
- `report-*.md` - Report 文档
- `audit-*.md` - Audit 文档

**访问方式**：
```bash
# V3 CLI
uv run python src/vibe3/cli.py flow show
uv run python src/vibe3/cli.py handoff show

# 数据库路径
$(git rev-parse --git-common-dir)/vibe3/handoff.db
```

#### V2 数据存储（`.git/vibe/`）

**`.git/vibe/registry.json`** - 任务注册表（跨项目共享）
- 记录所有任务的状态与当前 runtime 映射关系
- 所有 worktree 都访问同一个 registry
- 通过 `git rev-parse --git-common-dir` 定位

**`.git/vibe/worktrees.json`** - Worktree 映射表（跨项目共享）
- 记录 worktree 路径与任务的绑定关系
- 所有 worktree 都访问同一个映射表

**`.git/vibe/tasks/{task-id}/`** - 任务详细数据（跨项目共享）
- 每个任务的 `task.json` 详细配置
- 所有 worktree 共享访问

**访问方式**：
```bash
# V2 Shell
$(git rev-parse --git-common-dir)/vibe/registry.json

# 查看用户级全局配置目录
ls ~/.vibe/
```

### `docs/` - 人类文档区

**职责**：所有给人类阅读的文档。包含标准、PRD、Spec、Plan、Directive 与 Handoff。

| 目录 | 职责 | 备注 |
|------|------|------|
| `standards/` | **项目标准真源**。定义命名、术语、编码规范与工作流标准。 | Canonical Truth |
| `directives/` | **[V3 Active]** 指令集文档。包含 Executor、Manager 与 Supervisor 的具体执行指令。 | Execution Truth |
| `handoff/` | **[V3 Active]** 执行交接现场。存放 Handoff Artifacts、中间产物与执行结果证据。 | Artifact Store |
| `prds/` | **产品需求文档**。描述业务目标与核心数据流。 | Cognition |
| `specs/` | **技术规范**。接口契约与核心不变量。 | Spec |
| `plans/` | **执行计划**。上下文圈定与任务拆分。 | Plan |
| `reports/` | **执行报告**。审计结果与变更总结。 | Report |
| `decisions/` | **架构决策 (ADR)**。记录决策背景、理由与结果。 | Architecture |
| `archive/` | **历史文档归档**。存放过时或已完成的文档。 | Archive |

#### docs/standards/ - 标准和规范

| 文件 | 职责 | 状态 |
|------|------|------|
| [doc-organization.md](docs/standards/doc-organization.md) | 文档组织标准 | Active |
| [glossary.md](docs/standards/glossary.md) | 项目术语真源 | Active |
| [cognition-spec-dominion.md](docs/standards/cognition-spec-dominion.md) | 宪法大纲：Vibe Guard 流程定义 | Active |
| [v3/command-standard.md](docs/standards/v3/command-standard.md) | 共享状态命令标准 (V3) | Active |
| [v3/orchestra-runtime-standard.md](docs/standards/v3/orchestra-runtime-standard.md) | Orchestra 运行时与层级标准 | Active |
| [vibe3-role-checks-and-balances-standard.md](docs/archive/vibe3-role-checks-and-balances-standard.md) | 角色制衡架构标准 (由 [Human-Mirror](docs/standards/v3/human-mirror-architecture-philosophy.md) 取代，强引导至 V3 真源) | Deprecated |
| [vibe3-command-standard.md](docs/archive/v3/vibe3-command-standard.md) | 旧版命令标准 | Archived |

#### `docs/archive/` - 历史文档归档

**职责**：保留已完成任务、退役设计稿和历史方案，供后续备查，不作为当前真源

#### `docs/prds/` - 全局 PRD

**职责**：不针对特定任务的全局性产品需求文档

**核心文档**：
- `vibe-workflow-paradigm.md` - 总 PRD：Vibe Guard 范式

#### `docs/references/` - 外部参考资料

**职责**：存放从外部收集的参考资料

**内容类型**：
- 技术文档和论文
- 设计参考和案例研究
- 行业标准和最佳实践
- 第三方工具和框架文档

**用途**：为项目决策和实现提供外部知识支持，不属于项目自身文档

#### `docs/specs/` - 规范文档

**职责**：按 issue / feature 组织的规范与实现约束文档

**用途**：
- 记录具体问题的接口契约、边界行为和实现约束
- 与 `docs/prds/`、`docs/plans/`、`docs/reports/` 配合使用

#### `docs/plans/` - 执行计划

**职责**：需要长期保留的计划文档与推进记录

**用途**：
- 记录正式计划、分解步骤和阶段性推进
- 不再以统一任务镜像目录承载任务文档

#### `docs/reports/` - 报告与总结

**职责**：长期保留的报告、审计和复盘文档

**用途**：
- 记录结论、验证结果、审计摘要和阶段总结
- 供后续会话和人类读者稳定引用

### `debug/` - 调试与分析区

**职责**：存放调试信息、执行追踪快照、临时分析报告。

**内容**：
- `external-project-integration-debug.md` - 外部集成调试记录。
- 自动化生成的 `debug_*.py`/`debug_*.sh` 临时脚本。

### 📁 临时与本地目录 (Temporary Directories)

**职责**：存放运行时产生的、不应进入版本控制的本地临时数据。

| 路径 | 职责 | 备注 |
|------|------|------|
| `temp/` | 通用临时目录 | 被 `.gitignore` 排除 |
| `wt-*/` | 任务级 Git worktrees | 被 `.gitignore` 排除 |
| `.worktrees/` | 集中式 worktrees 存储 | 被 `.gitignore` 排除 |
| `tmpvibe-*` | 运行时临时前缀目录 | 被 `.gitignore` 排除 |

### `.kiro/` - Kiro Spec 工作区

**职责**：Kiro 的 spec 定义和工作文件

**结构**：
```
.kiro/
└── specs/
    └── {spec-name}/
        ├── .config.kiro
        ├── requirements.md
        ├── design.md
        └── tasks.md
```

## 🔄 文档更新流程

### 何时更新各文档

> **遵循单一事实原则**：只在权威文件中修改，其他文件通过引用保持同步。详见 [SOUL.md](SOUL.md) §7

| 文档 | 更新时机 | 权威内容 |
|------|---------|---------|
| `SOUL.md` | 核心原则变更（极少） | 价值观、边界、优先级、文档职责分工 |
| `STRUCTURE.md` | 添加/删除目录或核心文件 | 目录结构、文件职责 |
| `AGENTS.md` | 添加新的必读文档 | AI 入口导航 |
| `CLAUDE.md` | 技术栈变更、规则变更 | 技术栈、命令、硬规则 |
| `README.md` | 用户可见功能变更 | 功能介绍、快速开始 |
| `DEVELOPER.md` | 开发流程、工具变更 | 开发流程、工具使用 |
| `docs/README.md` | 文档结构变更 | 文档组织、导航 |
| `vibe3 handoff append` | 每个新任务 / skill 完成后 | 当前 flow handoff 状态（`vibe3 handoff show` 读取） |
| `claude-memory` MCP 工具 | 重要决策时 | 跨会话记忆：被动记忆通过 hooks 自动捕获 observations（`search`、`get_observations` 查询）；主动记忆通过 `build_corpus` 创建知识库，`prime_corpus` + `query_corpus` 查询 |

## 🎯 设计原则

### 单一事实来源（Single Source of Truth）

详见 [SOUL.md](SOUL.md) §0

每个概念只在一个文档中详细阐述：

| 概念 | 权威文件 |
|------|---------|
| 项目宪法和核心原则 | `SOUL.md` |
| 项目结构 | `STRUCTURE.md`（本文件） |
| AI 入口导航 | `AGENTS.md` |
| 技术栈和硬规则 | `CLAUDE.md` |
| 用户功能介绍 | `README.md` |
| 开发流程 | `DEVELOPER.md` |
| 文档组织标准 | `docs/standards/doc-organization.md` |
| 工作流范式 | `docs/prds/vibe-workflow-paradigm.md` |

### 人类 vs AI 分离

- **`docs/`** - 人类主权区，给人类阅读
- **`.agent/`** - AI 工作区，AI 的工具和规则

### 最小化原则

- 根目录文件尽可能少
- 每个文件职责单一
- 避免重复信息（通过引用而非复制）

## 📚 快速导航

### 我是新开发者
1. 阅读 `README.md` - 了解项目
2. 阅读 `DEVELOPER.md` - 了解开发流程
3. 阅读 `STRUCTURE.md`（本文件）- 了解项目结构
4. 阅读 `SOUL.md` - 了解核心原则
5. 查看 `src/vibe3/` - 了解 V3 Python 实现（主要）

### 我是 AI Agent
1. 阅读 `AGENTS.md` - 入口指南
2. 阅读 `CLAUDE.md` - 项目规则
3. 阅读 `SOUL.md` - 核心原则
4. 运行 `vibe3 handoff show` - 当前 handoff 状态

### 我要创建新任务
1. 阅读 `docs/README.md` - 文档结构
2. 阅读 `docs/standards/doc-organization.md` - 详细指南
3. 使用 `.agent/templates/` 中的模板
4. 运行 `git checkout -b <branch>` 创建分支，然后运行 `uv run python src/vibe3/cli.py flow update` 注册 flow

### 我要理解工作流
1. 阅读 `docs/prds/vibe-workflow-paradigm.md` - Vibe Guard 范式
2. 阅读 `docs/standards/cognition-spec-dominion.md` - 宪法大纲
3. 查看 `docs/specs/`、`docs/plans/` 和 `docs/reports/` 中的现有文档
4. 运行 `uv run python src/vibe3/cli.py flow --help` - 查看命令帮助

### 我要使用 V3 命令
```bash
# Flow 管理
uv run python src/vibe3/cli.py flow update
uv run python src/vibe3/cli.py flow show
uv run python src/vibe3/cli.py flow status

# Handoff 管理
uv run python src/vibe3/cli.py handoff init
uv run python src/vibe3/cli.py handoff show
uv run python src/vibe3/cli.py handoff append "message"

# 测试
uv run pytest
uv run pytest tests/vibe3/ -k flow
```

## 🔍 文件审查清单

定期审查以下内容，确保一致性：

- [ ] `STRUCTURE.md` 反映实际目录结构
- [ ] `AGENTS.md` 的 Essential Reading 列表完整
- [ ] `CLAUDE.md` 的参考链接有效
- [ ] `docs/README.md` 与实际文档结构一致
- [ ] `.agent/templates/` 包含所有必需模板
- [ ] 所有入口文件相互引用正确
- [ ] `src/vibe3/` 遵循 Python 编码标准
- [ ] `tests/vibe3/` 测试覆盖率 ≥ 80%
- [ ] `.git/vibe3/handoff.db` 结构与代码一致

## 📝 维护责任

详见 [SOUL.md](SOUL.md) §7 的完整维护责任表。

**核心原则**：
- 修改概念时，只修改权威文件
- 其他文件通过引用保持同步
- 定期审查，消除重复内容

---

**注意**：本文档的元数据（作者、创建日期、最后更新日期）已在文档开头的 frontmatter 中定义。详见 [docs/standards/doc-quality-standards.md](docs/standards/doc-quality-standards.md)。
tandards.md)。
