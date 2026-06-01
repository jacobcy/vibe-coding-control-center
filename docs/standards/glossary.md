---
document_type: standard
title: Project Glossary
status: approved
scope: terminology
authority:
  - project-terminology
  - term-boundaries
  - term-aliases
author: Codex GPT-5
created: 2026-03-08
last_updated: 2026-04-20
related_docs:
  - SOUL.md
  - CLAUDE.md
  - docs/README.md
  - docs/standards/action-verbs.md
  - docs/standards/v3/command-standard.md
  - docs/standards/v3/data-model-standard.md
  - docs/standards/v3/python-capability-design.md
  - docs/standards/v3/skill-standard.md
---

# 项目术语表

本文档是 Vibe Center 项目术语的唯一真源。

本文档只定义本项目内的特指语义，不展开通用百科解释。其他标准、入口文档、skills、workflows 若使用本文档已定义术语，只能引用，不得重新定义。

高频动作词见 [action-verbs.md](action-verbs.md)。

## 1. Governance

- 每个概念只能有一个正式术语
- `别称` 只用于识别历史语境，不作为并列正式叫法
- 发现术语模糊、误用或冲突时，优先修本文档，再修引用文档
- doc review 应检查：
  - 是否使用了未定义术语
  - 是否把别称当成正式术语
  - 是否把不同维度的术语混用

## 2. Term Axes

本项目术语按六个维度组织：

- 共享状态术语
- Git 与现场术语
- 系统职责术语
- 运行时层级术语
- 文档流程术语
- 调用面术语

禁止把不同维度的术语当作同一层概念使用。

## 3. Shared-State Terms

### 3.1 GitHub Issue

- 正式术语：`GitHub issue` 或简称 `issue`
- 别称：无（不再使用 “repo issue”）
- 定义：GitHub repository issue，可以是需求、任务、缺陷、讨论等。所有 issue 都是 GitHub 上的实体对象。
- 边界：
  - GitHub issue 不是 execution record
  - GitHub issue 不是 roadmap item
  - GitHub issue 不是 flow
- 落点：
  - 命令语义见 [command-standard.md](v3/command-standard.md)
  - task 关联字段见 [data-model-standard.md](v3/data-model-standard.md)
  - 标准规范见 [issue-standard.md](issue-standard.md)
- 使用规则：
  - 所有 issue 都是 GitHub repository issue
  - 讨论需求、任务、缺陷时统一使用 “issue” 或 “GitHub issue”
  - 不要区分 “repo issue” 和 “task issue”，它们都是 GitHub issue

### 3.2 `roadmap item`

- 正式术语：`roadmap item`
- 别称：`规划项`
- 定义：规划层工作单元概念，用于表达版本规划窗口中的工作项。
- 状态：**历史兼容 / 规划参考语义**。
- 边界：
  - `roadmap item` 仅为 planning 层概念，不是执行层真源。
  - 当前治理（Orchestra）直接管理 `assignee issue`，不经过 `roadmap item -> task` 中间层转换。
  - `roadmap.json` 与 `GitHub Project` 仅为历史兼容镜像，不作为主开发链锚点。
- 使用规则：
  - 仅在讨论版本排期（`p0/current/next/deferred/rejected`）时使用。
  - 不得将 roadmap 状态作为分支执行进度的判定依据。

### 3.3 `task`

- 正式术语：`task`
- 别称：`执行任务`
- 定义：execution bridge 概念，用于表达当前 flow 绑定的主执行 issue 及其关联执行事实。
- 边界：
  - `task` 不是外部需求入口。
  - `task` 不等于 PR，不等于 roadmap item。
- 使用规则：
  - 讨论可执行、可拆分、可绑定 flow 的工作单元时使用。
  - `task` 是 flow 建立后的 execution bridge，不是 roadmap item 的强制下游产物。
  - 它是执行现场的“任务视图”，不是用户默认主链的第一锚点。

### 3.3.1 task issue

- 正式术语：`task issue`
- 别称：无
- 定义：**vibe3 视角下的执行关系角色**。指被 vibe3 纳入 flow 管理的 `assignee issue`，且作为该 flow 的主执行目标。
- 判定标准：
  - 在 SQLite `flow_issue_links` 中有记录，且角色为 `task`。
  - 该 issue 必须属于 `assignee issue pool`。
- 边界：
  - **不是**新的 GitHub 对象类型。
  - **不是**与 GitHub issue 平行的实体。
  - `vibe-task` 标签是 flow bind 的自动镜像（副作用），不作为治理判定依据。
- 使用规则：
  - 不说 "创建 task issue"，而是 "将 issue 关联为 task"。
  - 它是相对于 flow 的**关系**，而不是 issue 的固有属性。

### 3.3.1a `orchestra-governed` (label)

- 正式术语：`orchestra-governed`
- 别称：无
- 定义：**治理决策镜像标签**。用于标记已通过 `assignee-pool` (Level 2 scan) 评估并做出确定性决策（如 ready/rfc/epic/close）的 issue。
- 职责：作为 governance 扫描的“已审查”标记，防止重复扫描，并作为三层治理体系（scanned -> governed -> reviewed）的中间状态。
- 边界：
  - **不是**自动化镜像，而是治理决策的显式标记。
  - 标记该 issue 已经过池内决策，无需再次 intake 或评估。
- 使用规则：
  - 由 `assignee-pool` 扫描完成后添加。
  - 人类手动移除此标签可使 issue 重新进入 governance 评估循环。

### 3.3.1b `orchestra-scanned` (label)

- 正式术语：`orchestra-scanned`
- 别称：无
- 定义：**Intake 审查镜像标签**。用于标记已通过 `roadmap-intake` (Level 1 scan) 审查但未被纳入执行池的 issue。
- 职责：标记该 issue 已被 intake 层处理（通常是跳过或拒绝），防止重复扫描。
- 边界：Level 1 治理标记。

### 3.3.1c `roadmap-reviewed` (label)

- 正式术语：`roadmap-reviewed`
- 别称：无
- 定义：**Roadmap 终审镜像标签**。用于标记已由 `vibe-roadmap` (Level 3 review) 完成终审决策的 issue。
- 职责：治理体系的终态标记，表示决策已固化并写入 memory。
- 边界：Level 3 治理标记。

### 3.3.2 `assignee issue`


- 正式术语：`assignee issue`
- 别称：无
- 定义：**本地开发链的处理对象**。指已进入执行池、由 Manager 主链（Plan/Run/Review）负责推进的 GitHub issue。
- 职责：它是当前 Governance (Orchestra) 事实观察的**真实且唯一范围**。
- 边界：
  - **不是** supervisor issue。
  - **不是** broader repo issue pool。
- 使用规则：
  - Manager 链只消费 `assignee issue`。
  - 当前 governance 排序与建议只针对此池。

### 3.3.3 `supervisor issue`

- 正式术语：`supervisor issue`
- 别称：无
- 定义：**本地治理链的处理对象**。指显式立项的治理任务（带 `supervisor` label），由 `supervisor/apply` 负责闭环。
- 边界：
  - **不进入** Manager 主开发链。
  - 用于文档治理、测试治理、环境清理等非业务开发动作。
- 使用规则：
  - `supervisor/apply` 只消费 `supervisor issue`。

### 3.3.4 `broader repo issue pool`

- 正式术语：`broader repo issue pool`
- 别称：无
- 定义：仓库中全量的开放 issue 或积压需求。
- 状态：roadmap governance 的 intake 输入池，也是 cron governance 的上游观察范围之一。
- 边界：
  - 不是 assignee issue pool。
  - 它不自动等于执行池。
- 使用规则：
  - roadmap governance 可从此池中把适合自动化推进的 issue 纳入 assignee issue pool。
  - cron governance 可从与文档治理相关的 broader repo 范围中形成 supervisor issue。
### 3.3.5 `check`

- 正式术语：`check`
- 别称：`handoff check`、`vibe task audit` (Legacy)
- 定义：`vibe3 check` 对 execution record (handoff artifact)、runtime 绑定证据和关联完整性进行审计/修复的动作。
- 边界：
  - `check` 不是 roadmap mirror 同步
  - `check` 不替 OpenSpec 或 plan 文档定义规划优先级
- 使用规则：
  - 讨论 task registry、handoff store、分支、OpenSpec、plans 的执行层核对时使用 `check`
  - 不要把 `check` 表述成 GitHub Project 同步

### 3.3.6 `OpenSpec 注册`

- 正式术语：`OpenSpec 注册`
- 别称：`OpenSpec execution spec 来源桥接`
- 定义：把 OpenSpec change 或 plan 文档作为 task 的 execution spec 来源写入 `spec_standard/spec_ref` 的动作。
- 边界：
  - `OpenSpec 注册` 不是 roadmap item 创建
  - `OpenSpec 注册` 不是 `roadmap sync`
- 使用规则：
  - 讨论 `spec_standard/spec_ref` 来源时使用 `OpenSpec 注册`
  - 不要把 OpenSpec change 直接说成 roadmap item 或 task 本体

### 3.3.7 `milestone`

- 正式术语：`milestone`
- 别称：无
- 定义：GitHub 标准中的版本或阶段窗口对象，也是本项目表达版本/阶段窗口的优先语义锚点。
- 边界：
  - `milestone` 不是 roadmap item type
  - `milestone` 不是 flow
- 落点：
  - 规划语义见 [command-standard.md](v3/command-standard.md)
  - 文件边界见 [github-labels-standard.md](github-labels-standard.md)
- 使用规则：
  - 讨论版本、阶段、交付窗口时优先使用 `milestone`
  - 历史上的 `version_goal` 应视为兼容字段，而不是长期上位概念

### 3.4 `flow`

- 正式术语：`flow`
- 别称：无
- 定义：对 branch 的逻辑交付现场包装，是 task 当前 execution scene 的表达。
- 边界：
  - `flow` 不等于 worktree
  - `flow` 不等于 branch，但开放 flow 默认以 branch 为身份锚点
  - `flow` 不是业务愿望本身
  - `flow` 不承担规划语义
- 落点：
  - 命令边界见 [command-standard.md](v3/command-standard.md)
  - 现场态边界见 [data-model-standard.md](v3/data-model-standard.md)
  - 状态定义：`flow_status` 字段在 `flow_state` 表
- 使用规则：
  - 讨论当前交付切片、由 branch 锚定且由 worktree 承载的任务现场时使用 `flow`
  - 讨论用户正在推进哪个目标时，默认优先从 `GitHub issue -> flow` 叙述
  - 不要把 `flow` 当作 `workflow`、`worktree` 或 `branch` 的同义词

### 3.4.1 Flow Status 语义

`flow_status` 定义了 flow 当前的执行状态，各状态语义：

- **`active`**：flow 正常执行中，准备就绪或正在处理。
- **`blocked`**：flow 被阻塞（手动锁定或依赖未满足）。属于 **BLOCK 系统**，表示工作流暂停。
  - 场景 1：**手动阻塞**（由人或 Manager 标记 `blocked_reason`），需要手动 unblock（通过 `vibe3 task resume` 等）。`blocked_reason` 的存在会阻止 QualifyGate 的自动解封。
  - 场景 2：**依赖阻塞**（`flow_issue_links` 中有未完成的依赖 Issue），由 Orchestra **自动恢复**。
  - 判定标准：依赖项在 GitHub 上进入 `closed` 终态即视为满足。
- **`done`**：flow 执行完成（PR 已合并）。
- **`stale`**：flow 长期未活动或被系统标记为休眠。
- **`aborted`**：flow 被人工/自动中止。

**ERROR 与 BLOCK 的正交关系**：

- **`failed` (ERROR System)**：指执行过程中发生了基础设施错误或异常。它记录在 `error_log` 中，影响 `FailedGate`（控制是否继续派发任务），但**不直接**改变 `flow_status`。
- **`blocked` (BLOCK System)**：指 Flow 的逻辑状态处于暂停。它可以是因为 `failed` 导致的副作用（如果业务逻辑决定报错后应阻塞），也可以是因为依赖未满足等正常业务逻辑。
- **关键区分**：一个 flow 可以有 `failed` 记录但仍处于 `active` 状态（例如重试中）；也可以处于 `blocked` 状态但没有任何 `failed` 记录（例如等待依赖）。

> `failed` 状态字面值已从 `flow_status` 中移除。Legacy 数据中的 `failed` 已迁移为 `active` 状态并配合 `blocked_reason` 表达。

### 3.4.2 `dependency` (issue role)

- 正式术语：`dependency` (issue role)
- 别称：依赖 issue
- 定义：在 `flow_issue_links` 表中，`issue_role = 'dependency'` 表示该 issue 是当前 flow 所依赖的前置任务。
- 语义：当前 flow 必须等待所有依赖 issue 完成（GitHub `issue.state == "closed"`）才能开始执行。
- 机制：
  - 依赖未满足 → flow 标记为 `blocked`。
  - 自动巡逻：Orchestra 每轮轮询时会检查依赖 Issue 状态。
  - 自动恢复：所有依赖满足后，Orchestra 自动移除阻塞，推断并恢复到正确状态。
  - 继承分支：解封 flow 的 worktree 默认从依赖的 PR 分支创建，确保代码基于最新依赖。

### 3.5 `pr`

- 正式术语：`pr`
- 别称：`pull request`
- 定义：本项目中 `pr` 默认特指 `GitHub Pull Request`，表示代码审查与合并交付单元。
- 边界：
  - `pr` 不是 task
  - `pr` 不是 flow
- 落点：
  - task 与 PR 的关系见 [data-model-standard.md](v3/data-model-standard.md)
- 使用规则：
  - 讨论代码评审与合并对象时使用 `pr`
  - 不要把 `pr` 当作需求或执行单元

## 4. Git And Runtime Terms

### 4.1 `worktree`

- 正式术语：`worktree`
- 别称：`工作树`、`工作目录`
- 定义：Git 的物理目录容器，是实际承载文件与未提交改动的现场。
- 边界：
  - `worktree` 不是 flow
  - `worktree` 不是 branch
- 落点：
  - 现场态边界见 [data-model-standard.md](v3/data-model-standard.md)
- 使用规则：
  - 讨论物理目录、当前文件现场、worktree 清理时使用 `worktree`

### 4.2 `branch`

- 正式术语：`branch`
- 别称：`分支`
- 定义：Git 开发线标识，用于承载提交历史。
- 边界：
  - `branch` 不是 flow
  - `branch` 不是 worktree
- 落点：
  - Git 工作流约束见 [git-workflow-standard.md](git-workflow-standard.md)
- 使用规则：
  - 讨论提交线、合并线、切分交付线时使用 `branch`

### 4.3 `workflow`

- 正式术语：`workflow`
- 别称：`工作流`
- 定义：描述一段业务过程、交付过程或 agent 处理过程的上层概念。
- 边界：
  - `workflow` 不等于 flow
  - `workflow` 不等于单个 branch
- 落点：
  - AI workflows 见 [../../.agent/README.md](../../.agent/README.md)
- 使用规则：
  - 讨论过程、阶段、交付路径时使用 `workflow`
  - 讨论运行时容器时不要用 `workflow` 代替 `flow`

### 4.4 Installation Lifecycle

- 正式术语：`installation lifecycle`
- 别称：`安装生命周期`
- 定义：首次安装、全局更新、项目初始化的职责分离：
  - **First-time setup** (`scripts/install.sh`): 引导全局目录、安装依赖、配置 shell
  - **Global update** (`vibe update`): 同步 repo 到 `~/.vibe`、清理陈旧文件
  - **Project initialization** (`scripts/init.sh`): worktree 特定设置、skills 安装
- 边界：
  - `install.sh` 不负责后续更新同步
  - `vibe update` 不负责首次环境引导
  - `scripts/init.sh` 不负责全局安装
- 落点：
  - 效果语义见 [../references/global-install-model.md](../references/global-install-model.md)
- 使用规则：
  - 讨论首次安装、环境引导时使用 `install.sh`
  - 讨论全局同步、更新分发时使用 `vibe update`
  - 讨论 worktree 初始化时使用 `scripts/init.sh`

### 4.5 Global Distribution

- 正式术语：`global distribution`
- 别称：`全局分发`
- 定义：位于 `~/.vibe` 的共享 Vibe 安装，供所有项目和工作树使用。包含：
  - V2 shell scripts (`bin/vibe`, `lib/`)
  - V3 Python code (`src/vibe3/`)
  - Configuration (`config/`)
  - User data (preserved: `keys.env`, `settings.yaml`)
- 边界：
  - `global distribution` 不等于 repo-local source
  - `global distribution` 不等于单个 worktree
- 使用规则：
  - 讨论全局安装位置、跨项目共享时使用 `global distribution`
  - 指定路径时写作 `~/.vibe`

### 4.6 Update Command

- 正式术语：`update command`
- 别称：`更新命令`
- 定义：V2 命令，用于幂等全局同步：
  - 同步核心组件从 repo 到 `~/.vibe`
  - 清理陈旧文件
  - 保留用户配置文件
  - 可安全多次运行
- 用法：`vibe update run [--dry-run] [--verbose]`
- 边界：
  - `update command` 不执行首次安装
  - `update command` 不修改 repo-local 源码
- 落点：
  - 命令实现见 `lib/update.sh`
- 使用规则：
  - 讨论全局同步、更新分发时使用 `update command`

### 4.7 Effect Semantics

- 正式术语：`effect semantics`
- 别称：`效果语义`
- 定义：决定变更何时生效的规则：
  - **Repo-local changes**: 当前 worktree 立即生效
  - **Global changes**: 需要 `vibe update`
  - **Shell loader changes**: 需要 `source ~/.zshrc`
  - **Python changes**: 当前 worktree 立即生效（cli.py 按 `__file__` 解析本地 `src/`，共享 venv 只装依赖），全局需要 `vibe update`
- 边界：
  - 效果语义不决定变更是否发生，只决定何时生效
- 落点：
  - 详细语义见 [../references/global-install-model.md](../references/global-install-model.md)
- 使用规则：
  - 讨论变更生效时机、同步需求时使用 `effect semantics`

### 4.8 Shared Venv

- 正式术语：`shared venv`
- 别称：`共享虚拟环境`
- 定义：位于 `~/.venvs/vibe-center` 的单一虚拟环境，由整个项目的所有 worktree 共用，**只安装第三方依赖**（`pyproject.toml` 设 `[tool.uv] package = false`，不安装 vibe3 包本身、无 editable `.pth`）。
- 代码解析：Python 代码按当前 worktree 本地解析，不依赖共享 venv：
  - `vibe3` wrapper 经 `cli.py` 的 `__file__` bootstrap 把本地 `src/` 置于 `sys.path` 首位（即使 `python -I`）
  - `uv run python -m ...` 等经提交的 `.envrc` 导出的 `PYTHONPATH=$PWD/src` 解析
- 边界：
  - `shared venv` 只提供依赖，不决定运行哪份代码
  - 不使用 per-worktree 独立 venv 或硬链接
- 落点：
  - 模型说明见 [../references/global-install-model.md](../references/global-install-model.md)
  - 回归测试见 `tests/vibe3/test_cli_bootstrap.py`
- 使用规则：
  - 讨论依赖隔离、跨 worktree venv 共享时使用 `shared venv`

## 5. System Responsibility Terms

### 5.1 Server 层

- 正式术语：`Server 层`
- 别称：`服务层`
- 定义：负责外部访问（HTTP/webhook）、健康检查和进程级 Driver 装配。
- 边界：
  - 不负责业务逻辑判断。
  - 不负责角色特有的派发规则。
- 落点：`src/vibe3/server/`

### 5.2 Runtime 层

- 正式术语：`Runtime 层`
- 别称：`运行时层`
- 定义：负责心跳（Heartbeat）、任务队列管理和事件路由。将外部观察（Observation）交由 Domain 层处理。
- 边界：
  - 不负责业务状态推进。
  - 不直接启动具体角色任务。
- 落点：`src/vibe3/runtime/`

### 5.3 Domain 层

- 正式术语：`Domain 层`
- 别称：`领域层`
- 定义：业务编排的唯一真源。定义领域事件，决定“下一步该发生什么”，驱动状态机。
- 边界：
  - 不直接操作 tmux/worktree 细节。
  - 不负责具体的执行细节。
- 落点：`src/vibe3/domain/`

### 5.4 Execution 层

- 正式术语：`Execution 层`
- 别称：`执行层`
- 定义：统一执行控制面。负责角色策略解析、容量控制（Capacity）、生命周期记录（Lifecycle）和 Session 真相写入。
- 边界：
  - 是 Domain 层的执行代理。
  - 不包含业务编排逻辑。
- 落点：`src/vibe3/execution/`

### 5.5 Environment 层

- 正式术语：`Environment 层`
- 别称：`环境层`
- 定义：负责环境原语（Worktree 创建/回收、tmux session 隔离）。
- 边界：
  - 不判断何时派发任务。
  - 不决定执行哪个角色。
- 落点：`src/vibe3/environment/`

### 5.6 `调度`

- 正式术语：`调度`
- 别称：无
- 定义：决定“下一个要推进什么”的活动，面向 feature、issue、roadmap item、task 的选择、排序和分组。
- 边界：
  - `调度` 不是代码执行
  - `调度` 不是单个 task 的步骤 organization
- 落点：
  - 命令边界见 [command-standard.md](v3/command-standard.md)
- 使用规则：
  - 讨论下一个 feature、task 分组、PR 切片时使用 `调度`

### 5.7 `编排`

- 正式术语：`编排`
- 别称：无
- 定义：决定“已选 task 如何进入执行过程”的活动，面向步骤顺序、命令组合、现场绑定与交付时机。
- 边界：
  - `编排` 不是调度
  - `编排` 不直接等于执行
- 落点：
  - skill 职责边界见 [python-capability-design.md](v3/python-capability-design.md)
- 使用规则：
  - 讨论先建 task 还是先开 flow、何时 bind/review/pr 时使用 `编排`

### 5.8 `执行代理`

- 正式术语：`执行代理`
- 别称：`执行器`
- 定义：实际写代码、改文档、跑测试、调用 shell 命令的 AI agent 实例，例如 `Claude Code`、`Codex`。
- 边界：
  - `执行代理` 不是 shell
  - `执行代理` 不是共享状态真源
  - `执行代理` 不应绕过 shell 直接写共享状态文件
- 落点：
  - AI 入口与规则见 [../../AGENTS.md](../../AGENTS.md)
  - 项目上下文见 [../../CLAUDE.md](../../CLAUDE.md)
- 使用规则：
  - 文档中优先使用 `执行代理`
  - `执行器` 只用于识别历史语境

### 5.9 Role Adapters (角色适配器)

- 正式术语：`Role Adapters`
- 别称：`Skill 层`, `胶水层`
- 定义：负责特定角色的输入组装、Prompt 渲染和结果解释。
- 边界：
  - 不应各自实现通用的派发（Dispatch）骨架。
  - 业务逻辑应收拢至 Domain 层，执行动作应收拢至 Execution 层。
- 落点：
  - 规则见 [skill-standard.md](v3/skill-standard.md)
  - 设计边界见 [python-capability-design.md](v3/python-capability-design.md)
- 使用规则：
  - 文档中优先使用 `Role Adapters`
  - `Skill 层` 作为历史叫法保留

### 5.9.1 Orchestra

- 正式术语：`Orchestra`
- 别称：`Orchestrator`
- 定义：本项目中的顶层编排与分诊角色适配器。负责多 issue / 多 flow 的事实观察、心跳治理、assignee 触发调度、队列管理和非 state label 治理。
- 核心机制：
  - **Heartbeat Tick**：Driver 进程内部的一次轮询循环，负责触发各 Service 的 `on_tick()`。
  - **Dispatch (派发)**：判定需要处理后，启动异步 child session（tmux）执行具体任务的动作。
- 边界：
  - `Orchestra` 不直接负责单个 flow 的执行逻辑
  - `Orchestra` 不直接写代码
  - `Orchestra` 不替 manager agent 决定固定的 plan / run / review 顺序
  - `Orchestra` 不把 `state label` 当作主触发源
  - **最终应收敛为薄适配层，不再持有业务真相**。
- 落点：
  - Python 模块：`src/vibe3/orchestra/`
  - Skill: `skills/vibe-orchestra/SKILL.md`


### 5.9.2 `Manager`

- 正式术语：`Manager`
- 别称：`Execution Proxy`, `执行负责人`
- 定义：本项目中的单 flow 状态控制角色适配器。负责将 issue 映射到 flow，提供 branch / worktree 现场创建、复用、清理和观察入口，以及管理 flow 生命周期相关的状态决策。
- 边界：
  - `Manager` 不负责多 issue 编排
  - `Manager` 不直接写代码
  - `Manager` 不替 agent 决定是否进入 plan、run、review、gh pr create 或 closeout
  - `Manager` 的清理能力不等于默认自动收口 workflow
  - **不再复写通用执行框架，其执行动作应交由 Execution 层**。
- 落点：
  - Python 模块：`src/vibe3/manager/`
  - Skill: `skills/vibe-manager/SKILL.md`

### 5.10 `Shell 能力层`

- 正式术语：`Shell 能力层`
- 别称：`capability layer`
- 定义：`vibe3` (Python) 和 `vibe` (V2 Shell) 暴露的原子、可组合、可验证方法层，是 skill 与共享状态真源之间的唯一合法操作通道。
- 边界：
  - `Shell 能力层` 不是 workflow engine
  - `Shell 能力层` 不是调度器
  - `Shell 能力层` 不是编排器
- 落点：
  - 定义见 [python-capability-design.md](v3/python-capability-design.md)
- 使用规则：
  - 讨论命令设计、原子能力、shell 边界时使用 `Shell 能力层`
  - **V3 Python (`vibe3`) 是当前主能力层**，负责 flow/handoff/orchestra 逻辑
  - **V2 Shell (`vibe`) 是次要/兼容层**，负责环境初始化、密钥管理和 legacy 工具

### 5.11 `共享状态真源`

- 正式术语：`共享状态真源`
- 别称：无
- 定义：项目共享状态的持久化数据真源集合，当前主要由 `vibe3` 管理，包括 SQLite 数据库（`handoff.db`）以及处于兼容期的 `registry.json`、`roadmap.json` 等。
- 边界：
  - `共享状态真源` 不是 shell
  - `共享状态真源` 不是 skill
  - `worktrees.json` 当前不是开放 flow 的主身份锚点
- 落点：
  - 边界见 [data-model-standard.md](v3/data-model-standard.md)
- 使用规则：
  - 讨论共享状态文件本身时使用 `共享状态真源`
  - `roadmap.json` 当前只按 mirror / cache / projection / backup 理解
  - 不要再用“物理真源”同时指 shell 和 JSON 文件

### 5.12 `shell 命令`

- 正式术语：`shell 命令`
- 别称：`vibe3 shell`, `vibe shell`
- 定义：通过 CLI 直接执行的命令能力。
  - **主命令 (V3)**：`vibe3 <subcommand>`。支持通过 `uv tool install -e .` 全局安装，或在项目内通过 `uv run python src/vibe3/cli.py` 调用。
  - **辅助命令 (V2)**：`vibe <domain> <subcommand>` (原 V2 shell 命令)
- 边界：
  - `shell 命令` 不是 skill
  - `shell 命令` 不是 workflow 文案本身
- 使用规则：
  - 文档和沟通中首次提及时，建议显式写成 `vibe3 flow (shell)` 这类格式
  - 优先调用 V3 命令，仅在环境管理等特定场景使用 V2 命令

### 5.13 `skill 命令`

- 正式术语：`skill 命令`
- 别称：`vibe skill`
- 定义：通过 Slash/workflow 触发的 skill 能力入口，例如 `/vibe-save`、`/vibe-new`。
- 边界：
  - `skill 命令` 不是 `bin/vibe` 的子命令
  - `skill 命令` 不应冒充 shell 命令语义
- 使用规则：
  - 文档和沟通中首次提及时，建议显式写成 `/vibe-save (skill)` 这类格式

### 5.14 `调用面标注规则`

- 当同一段内容同时出现 shell 与 skill 能力时，首次提及必须显式标注调用面：
  - `vibe flow (shell)`
  - `/vibe-save (skill)`
- 后续同段复用同一对象时可省略后缀，但跨段再次出现建议重标一次，避免歧义。

## 6. Runtime Hierarchy Terms

- **`Orchestra Driver`**：通过 `vibe3 serve start` 启动的长期运行主进程。
- **`Heartbeat Tick`**：Driver 内部的周期性轮询循环。
- **`Async Child Session`**：由 Tick 派发的、在独立 tmux session 中运行的异步子任务（如 manager run, governance scan）。
- **`Domain Event`**：Agent 执行生命周期的真源，负责驱动状态转换与副作用。

## 7. Document Process Terms

以下术语只属于文档流程层级，不属于运行时系统分层：

- `规范层`
- `执行计划层`
- `代码实现层`
- `AI审计层`

这些术语的流程定义见 [../README.md](../README.md) 与 [cognition-spec-dominion.md](cognition-spec-dominion.md)。

禁止把：

- `执行层`（task / execution state）
- `执行计划层`（plan 文档）

当作同一个概念。

### 7.1 Documentation Role Terms

#### `入口文件`

- 正式术语：`入口文件`
- 别称：无
- 定义：人类或执行代理进入项目时首先阅读的导航型文档。
- 边界：
  - `入口文件` 不是标准真源
  - `入口文件` 不应承载复杂规范全文
- 落点：
  - 根目录入口文件，如 [../../AGENTS.md](../../AGENTS.md)、[../../CLAUDE.md](../../CLAUDE.md)、[../../README.md](../../README.md)、[../../STRUCTURE.md](../../STRUCTURE.md)
- 使用规则：
  - 入口文件应提供导航、最小必要约束和引用链
  - 不在入口文件中堆叠复杂规范

#### `标准文件`

- 正式术语：`标准文件`
- 别称：无
- 定义：位于 `docs/standards/` 的项目内部稳定规范真源。
- 边界：
  - `标准文件` 不等于入口文件
  - `标准文件` 不记录临时讨论和执行噪音
- 落点：
  - [docs/standards/](.)
- 使用规则：
  - 讨论项目一致规范、稳定定义和边界时使用 `标准文件`

#### `参考文件`

- 正式术语：`参考文件`
- 别称：无
- 定义：位于 `docs/references/` 的外部知识、外部库和外部资料引用文档。
- 边界：
  - `参考文件` 不是项目内部规范真源
  - `参考文件` 不应反向定义项目标准
- 落点：
  - [docs/references/](../references)
- 使用规则：
  - 引用外部库、外部知识、外部资料时使用 `参考文件`

#### `规则文件`

- 正式术语：`规则文件`
- 别称：无
- 定义：位于 `.agent/rules/` 的 agent 执行规则、实现细则和模式约束文件。
- 边界：
  - `规则文件` 不是项目宪法
  - `规则文件` 不应重写标准文件或入口文件的概念真源
- 落点：
  - [.agent/rules/](../../.agent/rules)
- 使用规则：
  - 执行代理需要具体执行细则、实现边界和模式时使用 `规则文件`

## 8. Identity Tracking Terms

### 8.1 `署名`

- 正式术语：`署名`
- 别称：`Authorship`, `打卡`, `追加署名`
- 定义：在认知记录和大盘数据中声明参与贡献的身份记录。例如写入 `task.json` 的 `agent_log` 字段，或在 `vibe-save` 记录中主动附带的宣告（如 `@Agent-Claude: xxxx`），以及在 Commit Message 中追加的 `Co-authored-by`。
- 边界：
  - `署名` 是逻辑层（Tier 2/3）的概念。
  - `署名` 不是数字签名（Digital Signature）。
  - `署名` 不是物理的 Git Author。
- 落点：
  - `task.json` 中的 `agent_log` 字段。
  - Git Commit Message 中的 `Co-authored-by` 行。
- 使用规则：
  - 讨论 Agent 如何宣告自己的参与贡献时，统一使用**“署名”**。
  - “如果误用签名，指的也是署名，不是数字签名。”项目语境下默认口语中的签名等同于署名。

### 8.2 `物理签名`

- 正式术语：`物理签名`
- 别称：`Git Author`, `Alias`, `工作区身份`
- 定义：仅指 Git 仓库物理底层的作者信息（即通过 `git config user.name` 和 `user.email` 写入的数据）。这是强制的、排他的单一所有者标记。
- 边界：
  - `物理签名` 只能由用户在具体 worktree 中显式设定（例如 `git config user.name/user.email`）。
  - `物理签名` 不能代表所有参与接力的协作者。
- 落点：
  - Worktree 隔离的 `.git/config`。
- 使用规则：
  - 讨论底层谁在提交代码或初始化 Worktree 所记录的身份时，使用**“物理签名”**。

### 8.3 `actor`

- 正式术语：`actor`
- 别称：无
- 定义：执行具体操作的 Agent 或 Human 身份标识（格式通常为 `backend/model` 或用户标识）。
- 边界：
  - `actor` 回答“谁在做事”。
  - `actor` 不应包含系统组件或发起源标识（如 `orchestra`）。
- 落点：
  - SQLite `flow_state` 中的 `latest_actor` 字段。
  - `FlowEvent` 中的 `actor` 字段。

### 8.4 `initiated_by`

- 正式术语：`initiated_by`
- 别称：无
- 定义：Flow 或任务的发起源标识，说明是哪个系统组件或触发方式开启了该流程。
- 示例值：`orchestra:manager`、`manual`、`skill:vibe-new`。
- 边界：
  - `initiated_by` 回答“什么发起了流程”，与 `actor` 维度不同。
- 落点：
  - SQLite `flow_state` 中的 `initiated_by` 字段。

## 9. Common Confusions

以下混用是高风险错误：

  - GitHub issue != `task`（一个是对象，一个是关系）
  - `roadmap item` != `task`
  - `flow` != `workflow`
- `flow` != `worktree`
- `flow` != `branch`
- `Shell 能力层` != `共享状态真源`
- `调度` != `编排`
- `执行代理` != `Shell 能力层`

若后续 doc review 发现新的高频混用，应优先在本文档补充修正。

