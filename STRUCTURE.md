---
document_type: core-entry
authority:
  - project-structure
  - file-organization
audience: both
review_frequency: on-change
author: Claude Sonnet 4.5
created: 2024-01-15
last_updated: 2026-03-25
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

- **V3 (Python)** - 主要实现，Python 3.10+，路径 `src/vibe3/`
- **V2 (Shell)** - Shell 实现，Zsh，入口 `bin/vibe`

本文档以 **V3 为主视角**进行说明。

## 📁 根目录结构

```
vibe-center/
├── STRUCTURE.md                 # 本文件：项目结构定义（你在这里）
├── AGENTS.md                    # AI Agent 入口指南
├── CLAUDE.md                    # 项目上下文、技术栈、硬性规则
├── SOUL.md                      # 项目宪法和核心原则
├── DEVELOPER.md                 # 开发者指南
├── README.md                    # 项目介绍（面向用户）
│
├── bin/                         # CLI 入口
│   ├── vibe                     # V2 Shell 入口
│   └── vibe3                    # V3 Python 入口
│
├── src/vibe3/                   # V3 Python 实现（主要）
│   ├── cli.py                   # CLI 主入口
│   ├── commands/                # 命令实现
│   ├── services/                # 业务逻辑
│   ├── clients/                 # 外部客户端
│   ├── models/                  # 数据模型
│   ├── utils/                   # 工具函数
│   └── observability/           # 可观测性
│
├── lib/                         # V2 Shell 核心逻辑
│   ├── *.sh                     # 各功能模块
│   └── ...
│
├── config/                      # V2 配置文件
│   ├── keys/                    # API 密钥配置
│   └── aliases/                 # 命令别名
│
├── tests/                       # 测试
│   ├── vibe3/                   # V3 测试
│   └── vibe2/                   # V2 测试
│
├── skills/                      # 技能定义（canonical source）
│   └── */                       # 各技能目录
│
├── .agent/                      # AI 工作区
│   ├── README.md                # AI 工作区说明
│   ├── context/                 # AI 上下文
│   │   ├── task.md              # [UNTRACKED] 由 vibe3 handoff 命令管理，不直接编辑
│   │   └── memory.md            # [TRACKED] 跨项目长期记忆与架构共识
│   ├── rules/                   # 编码规则
│   │   ├── coding-standards.md  # 编码标准
│   │   ├── python-standards.md  # Python 标准（V3 权威）
│   │   └── patterns.md          # 设计模式
│   ├── templates/               # 文档模板（AI 工具）
│   │   ├── prd.md               # PRD 模板
│   │   ├── tech-spec.md         # Spec 模板
│   │   ├── plan.md              # Plan 模板
│   │   ├── test.md              # Test 模板
│   │   ├── code.md              # Code 模板
│   │   ├── audit.md             # Audit 模板
│   │   └── task-readme.md       # Task README 模板
│   ├── workflows/               # 工作流定义
│   └── skills/                  # 技能运行时（symlinks）
│
├── docs/                        # 人类文档区
│   ├── README.md                # 文档总览
│   ├── standards/               # 标准和规范
│   │   ├── DOC_ORGANIZATION.md  # 文档组织标准
│   │   ├── cognition-spec-dominion.md  # 宪法大纲
│   │   └── ...                         # 其他现行标准
│   ├── prds/                    # 全局 PRD
│   │   ├── vibe-workflow-paradigm.md   # 总 PRD
│   │   └── ...
│   ├── references/              # 外部参考资料
│   │   └── ...                  # 收集的外部文档、论文、资料等
│   ├── archive/                 # 历史文档归档
│   │   └── ...                  # 已退役设计与历史任务文档
│   └── tasks/                   # 任务文档
│       └── {Task_ID}/           # 各任务目录
│
└── .kiro/                       # Kiro Spec 工作区
    └── specs/                   # Spec 定义
        └── */                   # 各 spec 目录
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

**职责**：Vibe 的主要实现，Python 3.10+

**规则**：
- 使用 `uv` 进行依赖管理
- 禁止使用 `python`/`pip`，必须用 `uv run`
- 详细标准见 [.agent/rules/python-standards.md](.agent/rules/python-standards.md)

**主要模块**：
- `cli.py` - CLI 主入口（Typer 路由分发）
- `agents/` - AI Agent 调用层（plan/review/run pipeline + backends）
- `analysis/` - 代码智能（symbol 分析、结构快照、变更范围）
- `clients/` - 外部系统客户端（Git, GitHub, AI, Serena, SQLite）
- `commands/` - CLI 子命令实现
- `config/` - 配置加载与 Pydantic schema 验证
- `exceptions/` - 统一异常层级
- `manager/` - Orchestra 执行代理（flow 映射、命令构建、worktree）
- `models/` - Pydantic 领域数据模型
- `observability/` - 日志、链路追踪、审计
- `orchestra/` - 编排中枢（issue 分诊、事件调度）
- `prompts/` - Prompt 模板组装与变量解析
- `runtime/` - 事件驱动运行时（EventBus, Heartbeat）
- `server/` - HTTP 服务层（webhook, MCP, health check）
- `services/` - 核心业务逻辑（flow/PR/task/handoff/check）
- `ui/` - CLI 输出格式化（Rich 渲染）
- `utils/` - 通用工具函数

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

### `config/` - V2 配置文件

**职责**：V2 Shell 实现的配置文件

**子目录**：
- `keys/` - API 密钥配置
- `aliases/` - 命令别名

### `tests/` - 测试

**职责**：所有测试代码

**子目录**：
- `vibe3/` - V3 Python 测试
- `vibe2/` - V2 Shell 测试

**规则**：
- V3 测试使用 pytest
- 测试覆盖率目标 80%+

### `skills/` - 技能定义

**职责**：技能的 canonical source（权威来源）

**规则**：
- 每个技能一个子目录
- 包含 `SKILL.md` 定义文件
- 运行时通过 symlink 链接到 `.agent/skills/`

### `.agent/` - AI 工作区

**职责**：AI Agent 的工作环境

**重要性**：这是 AI 的"办公室"，包含所有 AI 需要的工具和规则

#### `.agent/context/` - AI 上下文

| 文件 | 职责 | 更新频率 |
|------|------|---------|
| `task.md` | **[UNTRACKED]** 当前 flow handoff 草稿、阻塞点、短期 TODO（已放入 .gitignore 隔离，通过 `vibe3 handoff` 命令访问，不直接编辑） | 每个动作后 |
| `memory.md` | **[TRACKED]** 长期共识、跨项目的架构决策池 | 重要架构决策时 |

#### `.agent/rules/` - 编码规则

| 文件 | 职责 |
|------|------|
| `coding-standards.md` | 编码标准 |
| `patterns.md` | 设计模式 |

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

#### `.agent/skills/` - 技能运行时

**职责**：技能的运行时环境（symlinks 到 `skills/`）

### `.git/vibe3/`、`.git/vibe/`、`~/.vibe/` - 数据存储

**职责**：Vibe 系统的数据存储位置

#### 数据存储位置规则

| 路径 | 职责 | 共享范围 | 版本 | 示例内容 |
|------|------|---------|------|---------|
| **`.git/vibe3/`** | **V3 运行时共享真源**（主仓库） | 所有 worktrees 共享 | V3 | `flow.db`, `handoff/*/` |
| **`.git/vibe/`** | **V2 运行时共享真源**（主仓库） | 所有 worktrees 共享 | V2 | `registry.json`, `worktrees.json`, `tasks/*/` |
| **`~/.vibe/`** | **用户级全局配置** | 当前用户跨仓库共享 | V2/V3 | loader、keys、skills 偏好 |
| **`<worktree>/.vibe/`** | **历史本地缓存方案（已淘汰）** | 仅历史文档背景 | V2 | 不再作为当前运行时真源 |

#### V3 数据存储（`.git/vibe3/`）

**`.git/vibe3/flow.db`** - SQLite 数据库（跨项目共享）
- 存储所有 flow 状态和事件
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
$(git rev-parse --git-common-dir)/vibe3/flow.db
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

**职责**：所有给人类阅读的文档

**重要性**：这是人类主权区，AI 只读不写

**详细结构**：见 [docs/README.md](docs/README.md)

#### `docs/standards/` - 标准和规范

| 文件 | 职责 |
|------|------|
| `DOC_ORGANIZATION.md` | 文档组织标准 |
| `cognition-spec-dominion.md` | 宪法大纲：Vibe Guard 流程定义 |

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

#### `docs/tasks/` - 任务文档

**职责**：每个任务的完整 Vibe Guard 文档

**命名格式**：`YYYY-MM-DD-feature-name`

**文档结构**：
```
{Task_ID}/
├── README.md               # 任务概述、状态、导航
├── prd-v1-initial.md       # PRD 层
├── spec-v1-initial.md      # Spec 层
├── plan-v1-initial.md      # Plan 层
├── test-strategy.md        # Test 层
├── code-implementation.md  # Code 层
└── audit-2024-01-15.md     # Review 层
```

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
| `.agent/context/memory.md` | 重要决策时 | 历史决策记录 |

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
| 文档组织标准 | `docs/standards/DOC_ORGANIZATION.md` |
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
2. 阅读 `docs/standards/DOC_ORGANIZATION.md` - 详细指南
3. 使用 `.agent/templates/` 中的模板
4. 运行 `uv run python src/vibe3/cli.py flow start <feature>` - 启动新 flow

### 我要理解工作流
1. 阅读 `docs/prds/vibe-workflow-paradigm.md` - Vibe Guard 范式
2. 阅读 `docs/standards/cognition-spec-dominion.md` - 宪法大纲
3. 查看 `docs/tasks/` 中的示例任务
4. 运行 `uv run python src/vibe3/cli.py flow --help` - 查看命令帮助

### 我要使用 V3 命令
```bash
# Flow 管理
uv run python src/vibe3/cli.py flow start <feature>
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
- [ ] `.git/vibe3/flow.db` 结构与代码一致

## 📝 维护责任

详见 [SOUL.md](SOUL.md) §7 的完整维护责任表。

**核心原则**：
- 修改概念时，只修改权威文件
- 其他文件通过引用保持同步
- 定期审查，消除重复内容

---

**注意**：本文档的元数据（作者、创建日期、最后更新日期）已在文档开头的 frontmatter 中定义。详见 [docs/standards/doc-quality-standards.md](docs/standards/doc-quality-standards.md)。
