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
last_updated: 2026-03-13
related_docs:
  - SOUL.md
  - CLAUDE.md
  - docs/README.md
  - docs/standards/action-verbs.md
  - docs/standards/v2/command-standard.md
  - docs/standards/v2/data-model-standard.md
  - docs/standards/v2/shell-capability-design.md
  - docs/standards/v2/skill-standard.md
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

本项目术语按五个维度组织：

- 共享状态术语
- Git 与现场术语
- 系统职责术语
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
  - 命令语义见 [command-standard.md](command-standard.md)
  - task 关联字段见 [registry-json-standard.md](registry-json-standard.md)
  - 标准规范见 [issue-standard.md](issue-standard.md)
- 使用规则：
  - 所有 issue 都是 GitHub repository issue
  - 讨论需求、任务、缺陷时统一使用 “issue” 或 “GitHub issue”
  - 不要区分 “repo issue” 和 “task issue”，它们都是 GitHub issue

### 3.2 `roadmap item`

- 正式术语：`roadmap item`
- 别称：`规划项`
- 定义：写入 `roadmap.json` 的规划层工作单元，是 mirrored `GitHub Project item` 的本地表达。
- 边界：
  - `roadmap item` 不是 execution record
  - `roadmap item` 不表达 branch/worktree 当前态
- 落点：
  - 规划语义见 [command-standard.md](command-standard.md)
  - 文件边界见 [roadmap-json-standard.md](roadmap-json-standard.md)
- 使用规则：
  - `feature` / `task` / `bug` 是 roadmap item 的 `type`
  - 讨论 `p0/current/next/deferred/rejected` 时使用 `roadmap item`
  - `roadmap item` 是 planning 中间层，不是用户默认主链锚点
  - 不要把 roadmap 状态当成分支当前执行状态

### 3.3 `task`

- 正式术语：`task`
- 别称：`执行任务`
- 定义：写入 `registry.json` 的 execution record，必须可执行、可跟踪、可绑定当前 flow。
- 边界：
  - `task` 不是外部需求入口
  - `task` 不等于 PR
  - `task` 不等于 roadmap item
- 落点：
  - 命令语义见 [command-standard.md](command-standard.md)
  - 文件字段见 [registry-json-standard.md](registry-json-standard.md)
- 使用规则：
  - 讨论可执行、可拆分、可绑定 flow 的工作单元时使用 `task`
  - 一个 `type=feature` 的 roadmap item 可以拆出多个本地 `task`
  - `task` 是 flow 建立后的 execution bridge，不是用户默认主链的第一锚点
  - GitHub issue 可以被关联为一个或多个 `task`（在不同 flow 中）

### 3.3.1 task issue

- 正式术语：`task issue`
- 别称：无
- 定义：**vibe3 视角概念**，指被 vibe3 管理的 GitHub issue。判定标准：
  - 在 SQLite `flow_issue_links` 中有记录，`issue_role = task` 或 `dependency`
  - GitHub issue 有 `vibe-task` 标签（由 vibe3 自动管理）
- 边界：
  - task issue **不是**新的 GitHub 对象类型
  - task issue **不是**与 GitHub issue 平行的新实体
  - task issue 是 GitHub issue 在 vibe3 管理视角下的**角色**
- 落点：
  - task 关联字段见 [registry-json-standard.md](registry-json-standard.md)
  - 命令语义见 [command-standard.md](command-standard.md)
  - 标准规范见 [issue-standard.md](issue-standard.md)
- 使用规则：
  - 不说 "创建 task issue"，而是 "将 issue 关联为 task"
  - task issue 是相对于 flow 的**关系**，不是 issue 的类型属性
  - 同一个 issue 可以在不同 flow 中有不同角色
  - PR 合并时会自动关闭关联的 task issue（联动操作）

### 3.3.2 `roadmap sync`

- 正式术语：`roadmap sync`
- 别称：无
- 定义：`vibe roadmap sync` 对 local roadmap items 与 GitHub Project items 做规划层 mirror 同步的动作。
- 边界：
  - `roadmap sync` 不是 execution record 注册
  - `roadmap sync` 不决定 task 拆分
- 使用规则：
  - 讨论 GitHub Project item mirror 对齐时使用 `roadmap sync`
  - 不要把 `roadmap sync` 当作 task intake 或 flow 编排入口

### 3.3.3 `task audit`

- 正式术语：`task audit`
- 别称：无
- 定义：`vibe task audit` 对 execution record、runtime 绑定证据和关联完整性进行审计/修复的动作。
- 边界：
  - `task audit` 不是 roadmap mirror 同步
  - `task audit` 不替 OpenSpec 或 plan 文档定义规划优先级
- 使用规则：
  - 讨论 task registry、分支、OpenSpec、plans 的执行层核对时使用 `task audit`
  - 不要把 `task audit` 表述成 GitHub Project 同步

### 3.3.4 `OpenSpec 注册`

- 正式术语：`OpenSpec 注册`
- 别称：`OpenSpec execution spec 来源桥接`
- 定义：把 OpenSpec change 或 plan 文档作为 task 的 execution spec 来源写入 `spec_standard/spec_ref` 的动作。
- 边界：
  - `OpenSpec 注册` 不是 roadmap item 创建
  - `OpenSpec 注册` 不是 `roadmap sync`
- 使用规则：
  - 讨论 `spec_standard/spec_ref` 来源时使用 `OpenSpec 注册`
  - 不要把 OpenSpec change 直接说成 roadmap item 或 task 本体

### 3.3.5 `milestone`

- 正式术语：`milestone`
- 别称：无
- 定义：GitHub 标准中的版本或阶段窗口对象，也是本项目表达版本/阶段窗口的优先语义锚点。
- 边界：
  - `milestone` 不是 roadmap item type
  - `milestone` 不是 flow
- 落点：
  - 规划语义见 [command-standard.md](command-standard.md)
  - 文件边界见 [roadmap-json-standard.md](roadmap-json-standard.md)
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
  - 命令边界见 [command-standard.md](command-standard.md)
  - 现场态边界见 [data-model-standard.md](data-model-standard.md)
- 使用规则：
  - 讨论当前交付切片、由 branch 锚定且由 worktree 承载的任务现场时使用 `flow`
  - 讨论用户正在推进哪个目标时，默认优先从 `repo issue -> flow` 叙述
  - 不要把 `flow` 当作 `workflow`、`worktree` 或 `branch` 的同义词

### 3.5 `pr`

- 正式术语：`pr`
- 别称：`pull request`
- 定义：本项目中 `pr` 默认特指 `GitHub Pull Request`，表示代码审查与合并交付单元。
- 边界：
  - `pr` 不是 task
  - `pr` 不是 flow
- 落点：
  - task 与 PR 的关系见 [registry-json-standard.md](registry-json-standard.md)
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
  - 现场态边界见 [data-model-standard.md](data-model-standard.md)
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

## 5. System Responsibility Terms

### 5.1 `调度`

- 正式术语：`调度`
- 别称：无
- 定义：决定“下一个要推进什么”的活动，面向 feature、issue、roadmap item、task 的选择、排序和分组。
- 边界：
  - `调度` 不是代码执行
  - `调度` 不是单个 task 的步骤组织
- 落点：
  - 命令边界见 [command-standard.md](command-standard.md)
- 使用规则：
  - 讨论下一个 feature、task 分组、PR 切片时使用 `调度`

### 5.2 `编排`

- 正式术语：`编排`
- 别称：无
- 定义：决定“已选 task 如何进入执行过程”的活动，面向步骤顺序、命令组合、现场绑定与交付时机。
- 边界：
  - `编排` 不是调度
  - `编排` 不直接等于执行
- 落点：
  - skill 职责边界见 [shell-capability-design.md](shell-capability-design.md)
- 使用规则：
  - 讨论先建 task 还是先开 flow、何时 bind/review/pr 时使用 `编排`

### 5.3 `执行代理`

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

### 5.4 `Skill 层`

- 正式术语：`Skill 层`
- 别称：`胶水层`
- 定义：负责理解上下文、调度、编排，并通过 shell 能力完成业务逻辑的技能层。
- 边界：
  - `Skill 层` 不是共享状态真源
  - `Skill 层` 不应直接写 JSON 真源
- 落点：
  - 规则见 [skill-standard.md](skill-standard.md)
  - 设计边界见 [shell-capability-design.md](shell-capability-design.md)
- 使用规则：
  - 文档中优先使用 `Skill 层`
  - `胶水层` 作为历史叫法保留

### 5.5 `Shell 能力层`

- 正式术语：`Shell 能力层`
- 别称：`capability layer`
- 定义：`vibe` shell 暴露的原子、可组合、可验证方法层，是 skill 与共享状态真源之间的唯一合法操作通道。
- 边界：
  - `Shell 能力层` 不是 workflow engine
  - `Shell 能力层` 不是调度器
  - `Shell 能力层` 不是编排器
- 落点：
  - 定义见 [shell-capability-design.md](shell-capability-design.md)
- 使用规则：
  - 讨论命令设计、原子能力、shell 边界时使用 `Shell 能力层`

### 5.6 `共享状态真源`

- 正式术语：`共享状态真源`
- 别称：无
- 定义：项目共享状态的持久化数据真源集合，当前包括 `registry.json`、`roadmap.json`、`flow-history.json`，以及处于兼容清退期的 `worktrees.json`。
- 边界：
  - `共享状态真源` 不是 shell
  - `共享状态真源` 不是 skill
  - `worktrees.json` 当前不是开放 flow 的主身份锚点
- 落点：
  - 边界见 [data-model-standard.md](data-model-standard.md)
- 使用规则：
  - 讨论共享状态文件本身时使用 `共享状态真源`
  - `roadmap.json` 当前只按 mirror / cache / projection / backup 理解
  - 不要再用“物理真源”同时指 shell 和 JSON 文件

### 5.7 `shell 命令`

- 正式术语：`shell 命令`
- 别称：`vibe shell`
- 定义：通过 CLI 直接执行的 `vibe <domain> <subcommand>` 命令能力，例如 `vibe flow`、`vibe task`、`vibe roadmap`。
- 边界：
  - `shell 命令` 不是 skill
  - `shell 命令` 不是 workflow 文案本身
- 使用规则：
  - 文档和沟通中首次提及时，建议显式写成 `vibe flow (shell)` 这类格式

### 5.8 `skill 命令`

- 正式术语：`skill 命令`
- 别称：`vibe skill`
- 定义：通过 Slash/workflow 触发的 skill 能力入口，例如 `/vibe-save`、`/vibe-new`。
- 边界：
  - `skill 命令` 不是 `bin/vibe` 的子命令
  - `skill 命令` 不应冒充 shell 命令语义
- 使用规则：
  - 文档和沟通中首次提及时，建议显式写成 `/vibe-save (skill)` 这类格式

### 5.9 `调用面标注规则`

- 当同一段内容同时出现 shell 与 skill 能力时，首次提及必须显式标注调用面：
  - `vibe flow (shell)`
  - `/vibe-save (skill)`
- 后续同段复用同一对象时可省略后缀，但跨段再次出现建议重标一次，避免歧义。

## 6. Document Process Terms

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

## 6.1 Documentation Role Terms

### `入口文件`

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

### `标准文件`

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

### `参考文件`

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

### `规则文件`

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

## 7. Identity Tracking Terms

### 7.1 `署名`

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

### 7.2 `物理签名`

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

## 8. Common Confusions

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
