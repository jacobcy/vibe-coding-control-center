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

## 目录职责
- `bin/`: CLI 分发入口
- `lib/`: Shell 核心逻辑
- `config/`: keys 与 aliases
- `skills/`: 治理与流程技能
- `.agent/`: rules/context/workflows

## HARD RULES
1. `lib/ + bin/` 总行数 <= 1200。
2. 单个 `.sh` 文件 <= 200 行。
3. 零死代码：函数必须有调用方。
4. 不在 shell 层实现排除项（NLP 路由、缓存系统、i18n、自研测试框架等）。
5. 能用现成工具就不用自造轮子（bats/jq/curl/gh）。
6. 新增能力必须符合 SOUL 的“认知优先”原则。
7. PR 说明必须附 LOC Diff（before/after/delta）。
8. **Git Workflow**：按 [git-workflow-standard.md](docs/standards/git-workflow-standard.md) 进行工作区管理，高频本地 Commit，未过 Audit Gate 严禁 `git push` 或建 PR，合入后强制销毁分支/worktree。
9. **Skill 管理**：只允许使用 `npx skills` 管理扩展，仅允许修改 `skills/` 目录内的自有 skill，严禁修改外部集成工具的自动生成文件。
10. **防污染原则**：严禁直接在终端或上下文中输出海量内容（如全量 `git diff`，直接 `cat` 大文件）。必须使用 Subagent 数据预处理、`head`/`tail` 截断或专门的提取脚本来提供摘要。

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
