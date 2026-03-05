# Project Context: Vibe Center 2.0

> **文档定位**：本文件提供项目上下文、技术栈和硬规则（详见 [SOUL.md](SOUL.md) §0 文档职责分工）
> **AI 入口**：AI Agent 请先阅读 [AGENTS.md](AGENTS.md)
> **文档结构**：详见 [docs/README.md](docs/README.md)

Vibe Center 是一个极简的 AI 开发编排工具：管理工具链、密钥、worktree/tmux 工作流，以及 Agent 规则体系。

## 技术栈
- 语言：Zsh
- 入口：`bin/vibe`
- 模块：`lib/*.sh`
- Agent 工作区：`.agent/`

## 常用命令
- `bin/vibe check`
- `bin/vibe tool`
- `bin/vibe keys <list|set|get|init>`
- `bin/vibe flow <start|review|pr|done|status|sync>`

## 架构分层 (三层解耦)
整个系统通过严格的三个抽象层解耦，以保证流程不越权、逻辑不混合：
1. **Tier 3 (认知层/流程编排): Supervisor (Vibe Gate)**
   - 相当于 OpenSpec / Serena / Superpower。
   - 负责全局的开发规范约束与流程管理（PRD -> Spec -> Test -> Code -> Audit）。
2. **Tier 2 (胶水层/智能辅助): Vibe Skills (Slash Commands)**
   - 即 `/vibe-task`, `/vibe-flow`, `/vibe-save` 等 Markdown 指令包装。
   - 位于 `.agent/skills/`，作为高阶的交互编排和认知组装。**它们是只读或调度器**，不允许直接修改底层数据结构（如 JSON 注册表）。
3. **Tier 1 (物理真源层/绝对执行): Shell Commands & Aliases**
   - 核心 Shell 命令组 (`bin/vibe <flow|task>`) 与底层 Alias 组 (`wtnew`, `vup`)。
   - 物理真源。数据的增删改查唯一通道。

## 目录职责
- `bin/`: CLI 分发入口
- `lib/`: Shell 核心逻辑（物理真源，操作 JSON 数据）
- `config/`: keys 与 aliases（低级快餐指令）
- `skills/`: Vibe Skills 智能辅助封装
- `.agent/`: rules/context/workflows（Supervisor 治理上下文）

## HARD RULES

### 代码规模与质量 (LOC & Quality)
1.  **LOC 限制**: `lib/ + bin/` 总行数 <= 2400。单文件 <= 200 行。
2.  **拒绝过度工程化**: 保持逻辑直觉与扁平化。严禁为了“解耦”而过度拆分或引入复杂的动态路由。
3.  **可读性优先**: 严禁为了满足行数限制而使用“丑陋”代码（如超长单行管道、混淆变量名）。
4.  **拆解优先**: 优先通过职责拆解（子文件、帮助文件）来管理体积，而非通过代码压缩。
5.  **一个文件，一个问题**: 每个 `.sh` 模块应有明确且单一的基础职责。
6.  **复杂逻辑外迁**: 超过 150 行或包含密集数据转换（如复杂的 `jq` 处理）的非核心逻辑应迁移至 `scripts/`。
7.  **人工审核**: 任何被界定为“复杂”的实现方案都必须在讨论模式中获得人工明确同意。
8.  **零死代码**: 函数必须有明确的调用方。

### Shell/Slash 职责边界
4. **Shell 职责与限制**：
   - 执行具体操作、脏活累活、确定性状态修改
   - 不实现复杂能力：NLP 路由、缓存系统、i18n、自研测试框架等
   - 优先用现成工具：bats/jq/curl/gh，不自造轮子

5. **Slash 职责与边界**：
   - 智能判断、交互编排、流程控制
   - 内部调用 Shell 命令执行具体操作
   - 优先使用现有 Shell 命令，只有 Shell 不具备的功能才手动 Edit
   - 严禁为已有 Shell 命令编写 Slash 层等价功能

6. **命令体系收敛**：优先在现有命令体系上补能力，不为单一场景随意新增顶层命令或 Slash 命令。

### 工作流程规范
7. **认知优先**：新增能力必须符合 SOUL 的”认知优先”原则。
8. **Git Workflow**：按 [git-workflow-standard.md](docs/standards/git-workflow-standard.md) 进行工作区管理，   - 高频本地 Commit
   - 未过 Audit Gate 严禁 `git push` 或建 PR
   - 合入后强制销毁分支/worktree
9. **Main 分支保护**：
   - **严禁直接在 main 分支修改代码**：main 分支只接受合并请求，不接受直接提交
   - **功能开发必须使用 feature 分支**：从 main 创建 feature 分支进行开发
   - **确保 main 分支始终处于可部署状态**
10. **PR 说明**：必须附 LOC Diff（before/after/delta）。

### 工具与扩展管理
10. **Skill 管理**：只允许使用 `npx skills` 管理扩展，仅允许修改 `skills/` 目录内的自有 skill，严禁修改外部集成工具的自动生成文件。

### 上下文与文件管理
11. **防污染原则**：严禁直接在终端或上下文中输出海量内容（如全量 `git diff`，直接 `cat` 大文件）。必须使用 Subagent 数据预处理、`head`/`tail` 截断或专门的提取脚本来提供摘要。
12. **临时文件与上下文隔离管理**：
    - **跨项目/长期全局记忆**：`.agent/context/memory.md` (追踪到 Git，用于团队/AI共享的设计决策池)。
    - **当前物理 Worktree 短期草稿**：`.agent/context/task.md` (必须在 `.gitignore` 中！仅用作短期 AI 上下文，包含当前 Blockers，重新构建时随时可从 `registry.json` 热重载)。
    - **跨 Worktree 共享文件**：写入 `.git/shared/` 目录，用于多 worktree 间的数据共享。
    - **禁止污染项目根目录**：不得在项目根目录随意创建临时文件或调试文件。

## 开发协议
- 思考英文，输出中文。
- 默认最小差异修改。
- 完成前必须给出验证证据（测试输出或可复现实验步骤）。

## 开发入口规则
当用户提出开发相关需求时（新功能、Bug修复、重构等），**必须**通过 `/vibe-new <feature>` 进入 vibe-orchestrator 流程：

**需要进入 vibe-new 的场景：**
- 用户说"帮我开发/实现/添加/修复/重构..."
- 用户描述了一个需要写代码的需求
- 用户提出的功能涉及修改代码

**不需要进入 vibe-new 的场景：**
- 纯问答（"怎么用..."、"什么是..."）
- 纯分析（"帮我分析..."、"看看这个..."）
- 纯文档阅读（"读一下..."、"总结一下..."）

**入口流程：**
1. 检测用户意图 → 开发相关需求
2. 调用 `/vibe-new <feature>` → 进入 vibe-orchestrator
3. vibe-orchestrator 的 Gate 0 会智能选择框架（Superpower/OpenSpec）
4. 按 Vibe Guard 流程执行

## 文档质量标准

所有文档应遵循统一的质量标准，使用 YAML frontmatter 标记元数据。

详见 **[docs/standards/doc-quality-standards.md](docs/standards/doc-quality-standards.md)**（权威标准）

**核心原则**：
- 每个文档必须有 frontmatter 元数据块
- AI Agent 创建文档时必须用真实身份签名（如 "Claude Sonnet 4.5"）
- 使用 `related_docs` 字段进行上下文圈定
- 每个字段必须有实际用途，不为标准而标准

## 参考

> **单一事实原则**：以下文档是各自领域的权威来源，详见 [SOUL.md](SOUL.md) §0

- **[SOUL.md](SOUL.md)** — 项目宪法和核心原则（权威）
- **[STRUCTURE.md](STRUCTURE.md)** — 项目结构定义（权威）
- **[AGENTS.md](AGENTS.md)** — AI Agent 入口指南
- **[docs/README.md](docs/README.md)** — 文档结构和标准
- **[docs/standards/doc-quality-standards.md](docs/standards/doc-quality-standards.md)** — 文档质量标准（权威）
- **[docs/standards/DOC_ORGANIZATION.md](docs/standards/DOC_ORGANIZATION.md)** — 文档组织标准详细指南
- **[.agent/README.md](.agent/README.md)** — AI 工作流和规则
- **[.agent/rules/*](.agent/rules/)** — 编码标准和模式
