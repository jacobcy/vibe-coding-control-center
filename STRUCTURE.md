---
document_type: core-entry
authority:
  - project-structure
  - file-organization
audience: both
review_frequency: on-change
author: Claude Sonnet 4.5
created: 2024-01-15
last_updated: 2025-01-24
related_docs:
  - SOUL.md
  - CLAUDE.md
  - docs/README.md
---

# Vibe Center 2.0 项目结构

本文档定义 Vibe Center 2.0 的完整项目结构，说明每个文件和目录的用途。

> **单一事实来源**：本文件是项目结构的权威定义。

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
│   └── vibe                     # 主命令入口
│
├── lib/                         # Shell 核心逻辑
│   ├── *.sh                     # 各功能模块
│   └── ...
│
├── config/                      # 配置文件
│   ├── keys/                    # API 密钥配置
│   └── aliases/                 # 命令别名
│
├── skills/                      # 技能定义（canonical source）
│   └── */                       # 各技能目录
│
├── .agent/                      # AI 工作区
│   ├── README.md                # AI 工作区说明
│   ├── context/                 # AI 上下文
│   │   ├── task.md              # 当前任务状态
│   │   └── memory.md            # 长期记忆
│   ├── rules/                   # 编码规则
│   │   ├── coding-standards.md  # 编码标准
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
│   │   └── vibe-engine-design.md       # 工作流引擎设计
│   ├── prds/                    # 全局 PRD
│   │   ├── vibe-workflow-paradigm.md   # 总 PRD
│   │   └── ...
│   ├── references/              # 外部参考资料
│   │   └── ...                  # 收集的外部文档、论文、资料等
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

**规则**：
- 只包含 `vibe` 主命令
- 负责参数解析和命令分发
- 不包含业务逻辑

### `lib/` - Shell 核心逻辑

**职责**：所有 Shell 脚本的业务逻辑

**规则**：
- 单文件 ≤ 200 行
- 总行数 ≤ 1200 行
- 零死代码：所有函数必须有调用方
- 模块化：每个 `.sh` 文件负责一个功能域

**主要模块**：
- `flow.sh` - Git worktree 工作流
- `tool.sh` - 工具链管理
- `keys.sh` - API 密钥管理
- `utils.sh` - 通用工具函数

### `config/` - 配置文件

**职责**：存放配置文件

**子目录**：
- `keys/` - API 密钥配置
- `aliases/` - 命令别名

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
| `task.md` | 当前任务状态 | 每个任务 |
| `memory.md` | 长期记忆和历史决策 | 重要决策时 |

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

### `docs/` - 人类文档区

**职责**：所有给人类阅读的文档

**重要性**：这是人类主权区，AI 只读不写

**详细结构**：见 [docs/README.md](docs/README.md)

#### `docs/standards/` - 标准和规范

| 文件 | 职责 |
|------|------|
| `DOC_ORGANIZATION.md` | 文档组织标准 |
| `cognition-spec-dominion.md` | 宪法大纲：六层流程定义 |
| `vibe-engine-design.md` | 工作流引擎设计 |

#### `docs/prds/` - 全局 PRD

**职责**：不针对特定任务的全局性产品需求文档

**核心文档**：
- `vibe-workflow-paradigm.md` - 总 PRD：六层六闸范式

#### `docs/references/` - 外部参考资料

**职责**：存放从外部收集的参考资料

**内容类型**：
- 技术文档和论文
- 设计参考和案例研究
- 行业标准和最佳实践
- 第三方工具和框架文档

**用途**：为项目决策和实现提供外部知识支持，不属于项目自身文档

#### `docs/tasks/` - 任务文档

**职责**：每个任务的完整六层文档

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
| `.agent/context/task.md` | 每个新任务 | 当前任务状态 |
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

### 我是 AI Agent
1. 阅读 `AGENTS.md` - 入口指南
2. 阅读 `CLAUDE.md` - 项目规则
3. 阅读 `SOUL.md` - 核心原则
4. 阅读 `.agent/context/task.md` - 当前任务

### 我要创建新任务
1. 阅读 `docs/README.md` - 文档结构
2. 阅读 `docs/standards/DOC_ORGANIZATION.md` - 详细指南
3. 使用 `.agent/templates/` 中的模板

### 我要理解工作流
1. 阅读 `docs/prds/vibe-workflow-paradigm.md` - 六层六闸范式
2. 阅读 `docs/standards/cognition-spec-dominion.md` - 宪法大纲
3. 查看 `docs/tasks/` 中的示例任务

## 🔍 文件审查清单

定期审查以下内容，确保一致性：

- [ ] `STRUCTURE.md` 反映实际目录结构
- [ ] `AGENTS.md` 的 Essential Reading 列表完整
- [ ] `CLAUDE.md` 的参考链接有效
- [ ] `docs/README.md` 与实际文档结构一致
- [ ] `.agent/templates/` 包含所有必需模板
- [ ] 所有入口文件相互引用正确

## 📝 维护责任

详见 [SOUL.md](SOUL.md) §7 的完整维护责任表。

**核心原则**：
- 修改概念时，只修改权威文件
- 其他文件通过引用保持同步
- 定期审查，消除重复内容

---

**注意**：本文档的元数据（作者、创建日期、最后更新日期）已在文档开头的 frontmatter 中定义。详见 [docs/standards/doc-quality-standards.md](docs/standards/doc-quality-standards.md)。
