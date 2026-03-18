# Project Context: Vibe Center 2.0

> **文档定位**：本文件提供项目上下文、技术栈和硬规则（详见 [SOUL.md](SOUL.md) §0 文档职责分工）
> **AI 入口**：AI Agent 请先阅读 [AGENTS.md](AGENTS.md)
> **术语真源**：项目术语以 [docs/standards/glossary.md](docs/standards/glossary.md) 为准
> **执行细则**：详细实现规则与执行模式见 [.agent/rules/coding-standards.md](.agent/rules/coding-standards.md) 和 [.agent/rules/patterns.md](.agent/rules/patterns.md)

Vibe Center 是一个极简的 AI 开发编排工具：管理工具链、密钥、worktree/tmux 工作流，以及 Agent 规则体系。

## 项目组成

本项目包含**两个并行实现**：

### V2 (Shell)
- **技术栈**：Zsh
- **入口**：`bin/vibe`
- **核心逻辑**：`lib/`
- **配置**：`config/`（keys、aliases）
- **状态**：`.git/vibe/`（共享状态真源）
- **测试**：`tests/vibe2/`

**常用命令**：
- `bin/vibe check` — 验证环境
- `bin/vibe tool` — 工具管理
- `bin/vibe keys <list|set|get|init>` — 密钥管理
- `bin/vibe flow <start|review|pr|done|status|sync>` — 流程管理

### V3 (Python)
- **技术栈**：Python 3.10+
- **路径**：`src/vibe3/`
- **依赖管理**：uv（**禁止使用 `python`/`pip`，必须用 `uv run`**）
- **测试**：`tests/vibe3/`
- **标准**：详见 [.agent/rules/python-standards.md](.agent/rules/python-standards.md)

**常用命令**：
- `uv run python src/vibe3/cli.py` — 运行 CLI
- `uv run pytest` — 运行测试
- `uv run mypy src/vibe3` — 类型检查

**格式化输出**（V3 新特性）：
- `uv run python src/vibe3/cli.py pr show --json` — JSON 格式输出
- `uv run python src/vibe3/cli.py pr show --yaml` — YAML 格式输出
- `uv run python src/vibe3/cli.py pr show --trace` — 带 trace 的结构化输出
- `uv run python src/vibe3/cli.py inspect commands pr show` — YAML 调用树（默认）
- `uv run python src/vibe3/cli.py inspect commands pr show --tree` — ASCII 树形
- `uv run python src/vibe3/cli.py inspect commands pr show --mermaid` — Mermaid 图表

## 架构分层

整个系统通过三个职责层解耦，以保证流程不越权、逻辑不混合。

本节只说明项目上下文，不重新定义术语；`Skill 层`、`Shell 能力层`、`共享状态真源` 等正式语义以 [docs/standards/glossary.md](docs/standards/glossary.md) 为准。

1. **Tier 3 (认知与治理): Supervisor (Vibe Gate)**
   - 负责开发规范约束、流程治理和阶段卡口。
2. **Tier 2 (Skill 层): Vibe Skills / Workflows**
   - 包括 `skills/`、`.agent/workflows/` 中的技能与工作流。
   - 负责理解上下文、调度和编排，但不直接写共享状态真源。
3. **Tier 1 (Shell 能力层): Shell Commands & Aliases**
   - 核心命令组 (`bin/vibe <flow|task|roadmap|check>`) 与底层 Alias 组 (`wtnew`, `vup`)。
   - 负责暴露原子能力，并作为操作共享状态真源的唯一合法通道。

## 目录职责

- `bin/`: CLI 分发入口（V2）
- `lib/`: Shell 核心逻辑（V2）
- `config/`: keys 与 aliases（V2）
- `skills/`: Vibe Skills 智能辅助封装
- `src/vibe3/`: Python 实现（V3）
- `tests/`: 测试（`tests/vibe2/` 和 `tests/vibe3/`）
- `.agent/`: rules/context/workflows（Supervisor 治理上下文）
- `.git/vibe/`: 共享状态真源（`roadmap.json`、`registry.json`、`worktrees.json`）

## HARD RULES

### 最小不可协商规则

1. **认知优先**：新增能力必须符合 [SOUL.md](SOUL.md) 的边界与原则。
2. **只走合法通道**：涉及共享状态时，优先通过 `vibe` Shell 能力层，不直接改底层真源。
3. **验证先于声称完成**：完成前必须提供测试输出、命令结果或可复现验证步骤。
4. **最小变更**：不做与当前任务无关的重构，不为单一场景随意扩命令体系。
5. **Git 纪律**：不直接在 `main` 上开发。
6. **调用面显式标注**：文档和沟通中首次提及 `vibe` 能力时，必须区分 `shell` 与 `skill`，例如 `vibe flow (shell)`、`/vibe-save (skill)`。
7. **handoff 不是真源**：`.agent/context/task.md` 只作本地 handoff；读取后必须先核查共享真源与 git 现场，若发现不一致必须修正。
8. **Agent 与 worktree 一对一**：一个 agent 只使用当前 worktree，不得自行跨 worktree 切换，也不得自行新建物理 worktree。
9. **PR 后禁止继续开发新目标**：当前 flow / worktree 已有 PR 时，agent 不得继续在其中开发新的交付目标；只允许处理 review follow-up、CI 修复和 handoff 记录。
10. **uv 必须使用**：Python 项目必须用 `uv run`，禁止 `python`/`pip` 命令。
11. **禁止 box drawing characters**：文档和输出中禁止使用线框图（┌ ─ │ └ ┘ 等），应使用 YAML、Mermaid 或简单 ASCII 符号（`=` `-` `|` `+`）。理由：Agent 解析友好、跨平台兼容。
12. **文件存放位置**：
    - **临时文件**：
      - Agent 生成的临时 reports → `.agent/reports/`（不被 git 追踪）
      - 其他临时测试文件、脚本 → `temp/`（不被 git 追踪）
    - **正式文档**：
      - 正式 plans → `docs/plans/`（被 git 追踪）
      - 正式 reports → `docs/reports/`（被 git 追踪）

详细规则见 [.agent/rules/coding-standards.md](.agent/rules/coding-standards.md)。

## 开发协议

- 思考英文，输出中文
- 默认最小差异修改
- 完成前必须给出验证证据（测试输出或可复现实验步骤）

## 执行模式

### 常规模式
- 默认使用完整流程：先讨论/计划，再实现
- 适用于新功能、重构、语义调整、影响面不明的修复

### 快速模式
- 仅在用户明确要求"快速模式"时启用
- 适用于紧急 bug 修复、共享状态损坏、必须先恢复可用性的场景
- 启用后可在确认需求后直接改代码，不强制先写计划或补测试
- 仍然必须：保持最小改动、提供验证步骤、说明未补测试的风险

## 开发入口规则

当用户提出开发相关需求时（新功能、Bug修复、重构等），**必须**通过 `/vibe-new <feature>` 进入 vibe-orchestrator 流程。

**需要进入 vibe-new 的场景**：
- 用户说"帮我开发/实现/添加/修复/重构..."
- 用户描述了一个需要写代码的需求
- 用户提出的功能涉及修改代码

**不需要进入 vibe-new 的场景**：
- 纯问答（"怎么用..."、"什么是..."）
- 纯分析（"帮我分析..."、"看看这个..."）
- 纯文档阅读（"读一下..."、"总结一下..."）

## 参考

> **单一事实原则**：以下文档是各自领域的权威来源，详见 [SOUL.md](SOUL.md) §0

- **[SOUL.md](SOUL.md)** — 项目宪法和核心原则（权威）
- **[STRUCTURE.md](STRUCTURE.md)** — 项目结构定义（权威）
- **[AGENTS.md](AGENTS.md)** — AI Agent 入口指南
- **[docs/standards/glossary.md](docs/standards/glossary.md)** — 项目术语真源（权威）
- **[.agent/rules/python-standards.md](.agent/rules/python-standards.md)** — Python 实现标准（权威）
- **[.agent/rules/coding-standards.md](.agent/rules/coding-standards.md)** — 实现与交付细则
- **[.agent/rules/patterns.md](.agent/rules/patterns.md)** — 执行模式与报告模式
- **[.agent/rules/kiro-integration.md](.agent/rules/kiro-integration.md)** — Kiro 集成规则