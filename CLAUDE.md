# Project Context: Vibe Center 3.0

> **文档定位**：本文件提供项目上下文、技术栈和硬规则（详见 [SOUL.md](SOUL.md) §0 文档职责分工）
> **AI 入口**：AI Agent 请先阅读 [AGENTS.md](AGENTS.md)
> **术语真源**：项目术语以 [docs/standards/glossary.md](docs/standards/glossary.md) 为准
> **执行细则**：详细实现规则与执行模式见 [.claude/rules/coding-standards.md](.claude/rules/coding-standards.md) 和 [.claude/rules/patterns.md](.claude/rules/patterns.md)

Vibe Center 是一个极简的 AI 开发编排工具：管理工具链、密钥、worktree/tmux 工作流，以及 Agent 规则体系。

## 项目组成

本项目包含**两个并行实现**：

### V2 (Shell)
- **技术栈**：Zsh
- **入口**：`bin/vibe`
- **核心逻辑**：`lib/`
- **配置**：`config/`（keys、aliases）
- **状态**：`.git/vibe/`（共享状态真源，位于主仓库 git common dir）
- **测试**：`tests/vibe2/`

**常用命令**：
- `bin/vibe doctor` — 环境诊断与依赖检查
- `bin/vibe update` — 全局分发同步（幂等）

> 现场确认与最小绑定操作已由 V3 接管；`task` 保留为内部桥接语义，优先使用 `uv run python src/vibe3/cli.py flow|task|handoff`。

### V3 (Python)
- **技术栈**：Python 3.12+
- **路径**：`src/vibe3/`
- **数据**：`.git/vibe3/handoff.db` 位于主仓库 git common dir，也就是主仓库 `.git`，不是当前 worktree 自己的局部 `.git`
- **依赖管理**：uv（**禁止使用 `python`/`pip`，必须用 `uv run`**）
- **运行环境**：所有 worktree 共用 venv `~/.venvs/vibe-center`（只装依赖，`package=false`，无 editable）；Python 代码按当前 worktree 本地解析（cli.py 的 `__file__` bootstrap + 提交的 `.envrc` 导出 `PYTHONPATH`）。详见 [docs/references/global-install-model.md](docs/references/global-install-model.md)
- **测试**：`tests/vibe3/`
- **标准**：详见 [.claude/rules/python-standards.md](.claude/rules/python-standards.md)

**常用命令**：
- `uv run python src/vibe3/cli.py` — 运行 CLI
- `uv run pytest` — 运行测试
- `uv run mypy src/vibe3` — 类型检查

**状态与运维命令**：
- `vibe3 flow status` — 查看所有活跃 flow 概览
- `vibe3 flow show` — 查看当前分支 flow 详情（`--branch <name>` 查看指定分支）
- `vibe3 flow rebuild` — 强制重建 issue flow scene (Destructive)
- `vibe3 flow bind` — 绑定 issue 到当前 flow
- `vibe3 task status` — 查看全局任务面板（推荐）
- `vibe3 task show` — 查看当前任务详情（可接 issue 编号）
- `vibe3 task intake` — 将 issue 分解/纳入本地管理
- `vibe3 task resume` — 恢复 blocked 任务（代替 flow unblock）
- `vibe3 inspect base` — 查看精确 Git 改动和 Review Kernel 最低审查等级
- `vibe3 serve status/start/stop/resume` — Orchestra 服务管理与 FailedGate 恢复
- `vibe3 scan` — 运行治理巡检（不启动服务）
- `vibe3 mcp` — 启动 MCP server
- `vibe3 ask` — 针对项目知识进行提问
- `vibe3 status` — [Compatibility] 兼容入口，优先使用 `vibe3 task status`

**代码分析工具**：
- `vibe3 inspect base/files/symbols` — Git 改动、单文件 AST 与已验证符号引用证据

**第三方工具**：
- `claude-plugin codex:rescue` — 利用codex调查代码缺陷
- `claude-plugin codex:review` — 利用codex进行代码评审
- `/claude-mem:mem-search` — claude-mem 跨会话记忆搜索（3-layer：search→timeline→get_observations；非 `claude-memory` CLI）
- `graphify query/explain` — 代码知识图谱（模块/社区/关系）
- `context7` — 库 API 官方文档（resolve-library-id → query-docs）
- `web_search_exa` — 外部最佳实践搜索
- 详细用法见 [supervisor/policies/common.md](supervisor/policies/common.md)「上下文工具」

## 架构分层

整个系统通过三个职责层解耦，以保证流程不越权、逻辑不混合。

本节只说明项目上下文，不重新定义术语；`Skill 层`、`Shell 能力层`、`共享状态真源` 等正式语义以 [docs/standards/glossary.md](docs/standards/glossary.md) 为准。

角色间的权力边界与制衡关系见 [docs/standards/v3/human-mirror-architecture-philosophy.md](docs/standards/v3/human-mirror-architecture-philosophy.md)。

1. **Tier 3 (认知与治理): Supervisor / Policies / Rules**
   - `supervisor/`：自动化编排角色材料，包含多个 roles（orchestrator, manager, auditor, rules-enforcer 等），只由 orchestration / manager 显式注入，不参与 skill discovery。
   - `supervisor/policies/`：`plan/run/review` 的 mode policy 与共享工具约束，按执行模式加载。
   - `.claude/rules/`：仓库长期规则、硬约束、实现标准。
2. **Tier 2 (Skill Layer): Vibe Skills / Workflows & Services**
   - 包括 `skills/`、`.agent/workflows/` 中的技能与工作流。
   - 核心组件：Manager Role, Agent Runners, Domain Handlers, Execution Coordinator, Services, Shared Module.
   - 负责业务编排、上下文管理、状态机转换与 Agent 执行调度。
   - **核心契约**：Shared Module 严禁反向导入 domain/ 或 execution/ 层，确保作为跨领域公共能力的单向依赖。
3. **Tier 1 (Shell 能力层): Shell Commands & Clients**
   - 核心命令组：V3 Python CLI (`vibe3`) 与 V2 Shell (`vibe`)；基础设施客户端（Git, GitHub, SQLite）。
   - 负责暴露原子能力、环境原语与共享状态真源的物理操作。

## 目录职责

- `bin/`: CLI 分发入口（V2）
- `lib/`: Shell 核心逻辑（V2）
- `config/`: keys 与 aliases（V2）
- `skills/`: 人机协作入口真源（agent 可发现）
- `supervisor/`: 自动化 manager / orchestra 角色材料（编排层显式注入）
- `src/vibe3/`: Python 实现（V3），包含以下子模块：
  - `cli.py` - CLI 主入口（Typer 路由分发）
  - `agents/` - AI Agent 执行层
    - `backends/` - Backend 实现（CodeagentBackend 等）
    - `plan/`, `run/`, `review/` - Agent pipeline
  - `analysis/` - 代码智能（symbol 分析、结构快照、变更范围）
  - `clients/` - 外部系统客户端
    - `protocols.py` - BackendProtocol（依赖注入接口）
    - `git_client.py`, `github_client.py`, `sqlite_client.py` 等
  - `commands/` - CLI 子命令实现
  - `config/` - 配置加载与 Pydantic schema 验证
  - `environment/` - 环境资源管理（统一抽象层）
    - `session_registry.py` - runtime_session registry
    - `worktree_manager.py` - worktree 管理
  - `execution/` - 执行控制平面（统一协调层）
    - `coordinator.py` - 统一的执行协调器（启动和追踪角色执行）
    - `capacity_service.py` - 容量控制服务
    - `execution_lifecycle.py` - 执行生命周期管理
    - `execution_role_policy.py` - 执行角色策略解析
    - `flow_dispatch.py` - Flow 分发逻辑
    - `gates.py`, `role_contracts.py` - 执行门禁和契约定义
  - `exceptions/` - 统一异常层级
  - `domain/` - 领域事件与 handlers
    - `events/` - Domain events
    - `handlers/` - Event handlers（manager, planner, executor, reviewer, supervisor）
    - `orchestration_facade.py` - 编排门面（事件发布）
  - `models/` - Pydantic 领域数据模型
  - `observability/` - 日志、链路追踪、审计
  - `orchestra/` - 编排中枢（issue 分诊、事件调度）
  - `prompts/` - Prompt 模板组装与变量解析
  - `roles/` - 角色定义和执行模块
    - `definitions.py` - 角色定义基类（RoleDefinition, TriggerableRoleDefinition）
    - `governance.py` - Governance 角色定义和请求构建器
    - `manager.py`, `plan.py`, `run.py`, `review.py` - 各角色定义和执行逻辑
    - `supervisor.py` - Supervisor 角色定义
    - `registry.py` - 角色注册表
  - `runtime/` - 事件驱动运行时（EventBus, Heartbeat）
  - `server/` - HTTP 服务层（webhook, MCP, health check）
  - `services/` - 核心业务逻辑（issue, pr, task, handoff, check）
    - `issue/`, `pr/`, `task/`, `handoff/` - 各领域业务逻辑
    - `shared/` - 跨领域公共能力层（labels, paths, errors, branches）
    - `protocols/` - 内部服务协议
  - `ui/` - CLI 输出格式化（Rich 渲染）
  - `utils/` - 通用工具函数
- `tests/`: 测试（`tests/vibe2/` 和 `tests/vibe3/`）
- `.agent/`: context/templates/workflows（AI 工作区：上下文、模板、工作流）
- `.git/vibe3/`: V3 共享状态（flow/task 元数据，位于主仓库 git common dir）。**严禁直接访问 `.git/vibe3/handoff/` 目录 (Worktree Handoff Restriction)，必须通过 `vibe3 handoff` 命令代理访问。**

## 分支与入口语义

仓库当前用两类分支区分人机协作与自动化执行现场：

- `dev/issue-<id>`：人机协作分支。默认通过 `skills/` 中的入口协作推进，例如 `/vibe-new`、`/vibe-continue`。
- `task/issue-<id>`：自动化分支。默认由 orchestra / manager 进入，并从 `supervisor/` 读取角色材料。

这条映射只定义默认入口语义，不改变 `plan/run/review` 的 mode policy：

- `plan/run/review` 继续从 `supervisor/policies/` 读取策略材料。
- `skills/` 与 `supervisor/` 定义”我是谁”。
- **策略材料分层**：
  - `supervisor/policies/` 定义”我现在处于什么执行模式”（跨项目通用，如验证原则、审查标准）
  - `.vibe/policies/` 定义本项目特定规则（追加到 supervisor/policies 同级文件之后，如 LOC limits 处理、测试数据库隔离）
- `.claude/rules/` 定义”整个仓库长期必须遵守什么”。

## HARD RULES

### 最小不可协商规则

1. **认知优先**：新增能力必须符合 [SOUL.md](SOUL.md) 的边界与原则。
2. **只走合法通道**：涉及共享状态时，优先通过 `vibe` Shell 能力层，不直接改底层真源。
3. **验证先于声称完成**：完成前必须提供测试输出、命令结果或可复现验证步骤。
4. **最小变更**：不做与当前任务无关的重构，不为单一场景随意扩命令体系。
5. **Git 纪律**：不直接在 `main`/`develop` 上开发，所有修改必须走 feature 分支
   - **正式提交**：创建 issue → `vibe3 internal bootstrap <issue> --branch dev/issue-<id>` → 开发 → PR
   - **快速提交**：`git checkout -b <branch> origin/main` → 提交 → PR（小改动、文档修正等）
   - **质量门禁**：所有提交经过 pre-commit，禁止 `--no-verify`；详情见 [coding-standards.md](.claude/rules/coding-standards.md) 交付纪律
6. **调用面显式标注**：文档和沟通中首次提及 `vibe` 能力时，必须区分 `shell` 与 `skill`，例如 `vibe flow (shell)`、`/vibe-save (skill)`。
7. **handoff 不是真源，但提供重要的 agent 交接上下文**：
   - **读取**：`vibe3 handoff show` 查看 agent 之间的事件记录和上下文交接
   - **写入**：`vibe3 handoff append <content>` 添加新的交接记录，为后续 agent 提供上下文
   - **注意**：handoff 记录只作补充，读取后必须先核查 `vibe3 flow show` 与 git 现场，若发现不一致必须修正
8. **Agent 与 worktree 一对一**：一个 agent 只操作当前 worktree，不得自行跨 worktree 切换。新建工作分支必须通过 `vibe3 internal bootstrap` 标准路径（snapshot baseline 已随 #3215 退役，bootstrap 现仅创建 worktree + flow scene，不再有不稳定副作用）；禁止手工 `git worktree add` 拼凑。
9. **PR 后禁止继续开发新目标**：当前 flow / worktree 已有 PR 时，agent 不得继续在其中开发新的交付目标；只允许处理 review follow-up、CI 修复和 handoff 记录。
10. **uv 必须使用**：Python 项目必须用 `uv run`，禁止 `python`/`pip` 命令。
11. **禁止 box drawing characters**：文档和输出中禁止使用线框图（┌ ─ │ └ ┘ 等），应使用 YAML、Mermaid 或简单 ASCII 符号（`=` `-` `|` `+`）。理由：Agent 解析友好、跨平台兼容。
12. **文件存放位置**：
    - **临时文件**：
      - Agent 生成的临时 plans → `.agent/plans/`（不被 git 追踪）
      - Agent 生成的临时 reports → `.agent/reports/`（不被 git 追踪）
      - 其他临时测试文件、脚本 → `temp/`（不被 git 追踪）
    - **长期留存**：
      - 任务描述 → GitHub issue
      - 需要留痕的结论 → issue comment / PR comment
13. **错误处理分类**（双轴正交，详见 [error-handling.md](docs/standards/error-handling.md)）：
    - 类层级（Axis A）：`SystemError`（系统故障，立即抛出 fail-fast）/ `UserError`（用户可操作恢复，`recoverable=True`）
    - `-y`/`--yes` 绕过由 **command 拥有**，`UserError` 不隐含可绕过
    - 批量续跑是**控制流模式**（收集 → 继续 → 统一报告），非异常类；不新增 `BatchError` 类
    - 严重度/门禁（Axis B）由 `ErrorHandlingContract` 拥有，与类层级正交
14. **本地测试节奏（CI 优先）**：
    - **本地避免全量测试**：本地默认执行**定向回归测试**，避免在同一轮修改中反复运行全量 `uv run pytest`。
    - **CI 优先原则**：全量测试交给线上 CI；创建 PR draft 后可直接查看 CI 结果，无需本地全量验证。
    - **本地全量测试场景**：仅在以下情况本地跑全量：
      - 用户明确要求
      - 需要复现 CI 特有失败
      - CI 环境不可用且必须验证
    - **增量修复策略**：若已跑过一次全量且失败点明确，后续应只跑失败相关子集直至修复完成，再交由 CI 复验。
15. **最短路径优先（复用优先于新增）**：
    - 新增功能前，必须先评估是否可通过现有命令/流程组合达到接近目标。
    - 若现有能力可低成本接入，应优先做”接线复用”，避免新增边缘命令或分叉逻辑。
    - 仅在必要且实现成本低时才新增能力；否则先提 issue，避免过度工程化。

16. **Skill-First 原则（命令准入门槛）**：
    - **默认路径是 Skill**：新增功能若本质是”编排现有命令并解释结果”，必须用 Skill 实现，禁止新增 Python 命令层代码。
    - **命令准入三问法**（全部通过才可考虑新增命令）：
      1. **是否创造不可替代的原子能力？**（状态写入、外部 API 调用、不可替代的计算）→ NO 则必须 Skill
      2. **Skill 编排现有命令能否达到 80% 目标？** → YES 则必须 Skill
      3. **是否属于核心管线阶段？**（plan/run/review 生命周期）→ YES 则必须是命令
    - **三问全过仍需人类明确授权**：Agent 不可自行决定新增 `vibe3 <command>`，必须在 Issue 中获得人类批准。
    - **轻量/重量判断**：轻量命令（简单代码，避免 Skill 偏差）值得做；但场景狭窄又超过 100 行复杂逻辑判断的命令，完全不值得做，必须退回 Skill。具体标准：
      - **值得做命令**：确定性强、逻辑简单（< 100 行核心代码）、Skill 调用会引入不必要偏差（如路径解析、状态原子写入）
      - **不值得做命令**：使用场景狭窄、需要大量条件分支和业务判断（> 100 行）、本质是"遍历检查项并汇报结果"
    - **核心管线不可迁移**：`plan.py`、`run.py`、`review.py` 是系统脊梁，内部复杂度通过 service 层重构解决，不上移到 Skill 层。
    - **诊断/检查类功能一律 Skill**：doctor、project-check、verify 等编排型功能，必须用 Skill 调用现有工具，不新增 Python 服务层。

17. **署名与操作身份规则**：
    - **原则**：尊重每个 Agent 的劳动成果，实行"逻辑署名与物理签名彻底脱钩"标准
    - **操作身份区分**（关键）：
      - **人类操作**：人类通过 Skill 入口（如 `/vibe-new`、`/vibe-continue`）发起的人机协作会话，由人类做关键决策
      - **Agent 操作**：GitHub 上以 `jacobcy` 账号执行的 Issue 创建、PR 发布、Comment 评论等，均为 Agent 在人类指导下完成，**不应视为人类直接操作**
      - **判断标准**：操作是否经过 Skill 入口、是否有人类实时交互决策 → 是则为人类操作；仅通过 API/CLI 自动执行 → Agent 操作
    - **要求**：
      - ✅ **Issue 创建**：必须记录创建者（通过 `/vibe-issue` 或手动标注）
      - ✅ **PR 创建**：必须在 PR body 中包含 Contributors 块
      - ✅ **Comment 发布**：必须明确标注发布者身份
    - **实施**：
      - Issue/PR 模板中包含署名字段
      - Flow state 自动记录 `planner/executor/reviewer/latest` backend/model
      - PR body 末尾自动生成 Contributors 列表
    - **详细规范**：[docs/standards/authorship-standard.md](docs/standards/authorship-standard.md)

18. **Secret Management（项目特定）**：
    - 本项目使用 `direnv` 管理环境变量（不使用 python-dotenv）
    - 原因：Shell + Python 混合项目，direnv 更通用
    - 禁止将密钥提交到 git（`.envrc` 已在 `.gitignore`）
    - 通用 Python 安全规范见：`~/.claude/rules/common/python-security.md`

19. **模块化与公开 API**：
    - 所有跨模块导入必须通过目标包的公开 API（`__init__` 导出），禁止深层导入
    - 新增导出必须符合允许类型（callable、dataclass 实例、Pydantic model、module re-export 等），不可随意导出裸实例
    - 详细规范见 [.claude/rules/modularity-standards.md](.claude/rules/modularity-standards.md)


## 开发协议

- 思考英文，输出中文
- 默认最小差异修改
- 完成前必须给出验证证据（测试输出或可复现实验步骤）

## 执行模式

项目遵循 **渐进披露原则**，详细执行模式见 [.claude/rules/patterns.md](.claude/rules/patterns.md)。

简要说明：
- **常规模式**（默认）：完整流程（计划 → TDD → 实现 → Code Review → Commit）
- **快速模式**（需用户明确要求）：最小改动 + 验证步骤，跳过部分流程

## Agent 工作流

**使用 `vibe3 run` 执行 AI Agent 任务**：

Vibe Center 通过 `vibe3 run` 命令集成 codeagent-wrapper，支持 AI Agent 执行开发任务。

**基本用法**：
```bash
# 方式 1：使用 plan 文件
vibe3 run --plan .agent/plans/my-plan.md

# 方式 2：直接传入指令（位置参数）
vibe3 run "Fix the bug in auth.py"
```

**重要**：
- **不要指定 `--agent`**，使用默认 agent 即可
- **两种方式二选一**：plan 文件或指令字符串

**标准流程**：
```
Plan → Run → Review → Commit
```

**详细规范**：
- **[docs/standards/agent-workflow-standard.md](docs/standards/agent-workflow-standard.md)** — Agent 工作流权威规范

**注意事项**：
- Agent 在正确的项目目录执行（通过 `cwd` 参数）
- Session 自动持久化到 flow（可通过 `vibe3 run --plan` 恢复）
- Agent 只操作当前 worktree（不会跨 worktree）
- 执行前必须有清晰的 plan 或 instructions
- 执行后必须审查代码修改并运行测试

## 基础设施服务

Vibe 3.0 提供统一的基础设施服务，支持所有执行角色（manager/planner/executor/reviewer）。

**核心服务**：
- **ExecutionRolePolicyService** - 统一的执行配置解析（backend、prompt、session）
- **CapacityService** - 统一的容量控制（解决双层节流问题）
- **ExecutionLifecycleService** - 统一的生命周期管理（started/completed/failed）
- **BackendProtocol** - Protocol-based dependency injection

**详细使用方法和 API 文档**：
- **[docs/v3/architecture/infrastructure-guide.md](docs/v3/architecture/infrastructure-guide.md)** — 基础设施使用指南
- **[docs/v3/architecture/capacity-control.md](docs/v3/architecture/capacity-control.md)** — 容量控制详解

---

## 开发入口规则

当用户提出开发相关需求时（新功能、Bug修复、重构等），**必须**通过 `/vibe-new <feature>` 进入标准开发准备流程。

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

**权威文档**：
- **[SOUL.md](SOUL.md)** — 项目宪法和核心原则（权威）
- **[STRUCTURE.md](STRUCTURE.md)** — 项目结构定义（权威）
- **[AGENTS.md](AGENTS.md)** — AI Agent 入口指南
- **[docs/standards/glossary.md](docs/standards/glossary.md)** — 项目术语真源（权威）
- **[docs/decisions/INDEX.md](docs/decisions/INDEX.md)** — 架构决策记录 (ADR)

**规则与标准**：
- **[.claude/rules/README.md](.claude/rules/README.md)** — 规则文件索引
- **[supervisor/policies/README.md](supervisor/policies/README.md)** — Mode policy 文件索引
- **[.claude/rules/coding-standards.md](.claude/rules/coding-standards.md)** — 实现与交付细则
- **[.claude/rules/python-standards.md](.claude/rules/python-standards.md)** — Python 实现标准（权威）
- **[.claude/rules/patterns.md](.claude/rules/patterns.md)** — 执行模式与报告模式
- **[.claude/rules/modularity-standards.md](.claude/rules/modularity-standards.md)** — 模块化标准（公开 API、导出类型、lazy import）
- **[docs/standards/agent-workflow-standard.md](docs/standards/agent-workflow-standard.md)** — Agent 工作流规范（权威）

<!-- BEGIN spec-kit context -->
## Spec-Kit 工作流（规范驱动开发）

本项目使用 [spec-kit](https://github.com/github/spec-kit)。非平凡变更 SHOULD 走六阶段：
`brainstorm → specify → plan → tasks → implement → review`。

- 治理真源：[`.specify/memory/constitution.md`](.specify/memory/constitution.md)
  （治理 spec-kit 使用；权限低于 SOUL.md / CLAUDE.md / `.claude/rules/*`）
- 规格目录：`.specify/specs/NNN-<slug>/`
- 可用 skills：`/speckit-*`（如 `/speckit-plan`、`/speckit-specify`、`/speckit-implement`），或 `specify workflow run speckit` 串联六阶段
- **双轨模型**：spec-kit（spec-driven 人机协作）与 vibe3 flow（issue-driven 自动化）并行，经 `after_*` hooks 桥接，不互相驱动。选用决策见 [docs/standards/spec-kit-workflow-standard.md](docs/standards/spec-kit-workflow-standard.md)
<!-- END spec-kit context -->

## graphify

本项目使用 [graphify](https://github.com/github/graphify) 构建代码知识图谱。图数据位于 `graphify-out/`，包含核心抽象 (god nodes)、社区结构和跨文件关系。

### 使用规则

- **代码查询优先走图**：`graphify query "<问题>"` 返回带上下文的子图，比 grep 更精准
- **关系/路径查询**：`graphify path "<A>" "<B>"` — 两概念间最短路径；`graphify explain "<节点ID>"` — 节点解释
- **架构概览**：`graphify-out/GRAPH_REPORT.md` 包含社区标签、god nodes 和意外连接分析
- **功能分支不提交 `graphify-out/`**：本地 hook 产生的图谱改动不进入普通功能 PR
- **合并后统一更新**：`Graphify Sync` workflow 在非图谱改动进入 `main` 后使用固定版本重建，并维护独立的 generated-artifact PR
- **人工更新仅用于诊断**：可运行 `graphify update .` 验证图谱，但不要把生成物混入功能提交
- **自动 PR 凭据**：必须配置 secret `GRAPHIFY_SYNC_TOKEN`（GitHub App/PAT，具备 contents 与 pull requests 写权限）；workflow 在缺失时直接失败，禁止回退到无法正常触发 required CI 的 `GITHUB_TOKEN`
