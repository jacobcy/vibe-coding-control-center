---
document_type: standard
title: Agent Workflow Standard
status: active
scope: agent-workflow-governance
authority:
  - agent-workflow-definition
  - agent-workflow-boundary
  - workflow-skill-relationship
author: Codex GPT-5
created: 2026-03-11
last_updated: 2026-03-11
related_docs:
  - AGENTS.md
  - CLAUDE.md
  - .agent/README.md
  - docs/standards/glossary.md
  - docs/standards/action-verbs.md
  - docs/standards/v2/skill-standard.md
  - docs/standards/v2/skill-trigger-standard.md
  - docs/standards/v2/command-standard.md
  - docs/standards/v2/shell-capability-design.md
---

# Agent Workflow Standard

本文档只定义 `.agent/workflows/*.md` 的治理边界。

本文所说的 `agent workflow`：

- 是面向执行代理的流程文件
- 是 slash / command 风格入口的语义文档
- 是 workflow 层的编排入口

本文**不**定义以下对象：

- GitHub Actions workflow
- GitHub Project workflow
- 项目交付流程的全部业务真源
- shell 命令能力本身

若出现这些概念冲突，以 `docs/standards/glossary.md` 为准。

## 1. 定义

### 1.1 `agent workflow`

- 正式术语：`agent workflow`
- 定义：位于 `.agent/workflows/` 的入口型流程文件，用于告诉执行代理：
  - 这个入口在处理什么对象
  - 应该委托哪个 skill / shell
  - 何时停止
  - 何时切到下一个入口

边界：

- `agent workflow` 不是 shell 命令
- `agent workflow` 不是 skill
- `agent workflow` 不是 GitHub workflow
- `agent workflow` 不是 roadmap / project / release 的业务对象

### 1.2 `workflow entry`

- 定义：用户触发的入口名，例如 `/vibe-new`
- 作用：把自然语言或 slash 请求路由到对应的 workflow 文档

### 1.3 `alias workflow`

- 定义：不拥有独立业务逻辑，只是把一个历史入口或兼容入口转发到另一条 workflow / skill 路径的薄入口
- 例子：
  - 历史入口保留
  - 兼容别名
  - 更窄场景下的快捷入口

`alias workflow` 可以没有同名 skill。

### 1.4 `standalone orchestration workflow`

- 定义：只做编排、路由、提示和停点判断的 workflow，本身不要求有同名 skill
- 使用场景：
  - 它只是一个 alias
  - 它只是把用户引导到已有 skill / shell 组合
  - 它本身没有独立业务逻辑真源

### 1.5 `skill-backed workflow`

- 定义：主要职责是把用户入口委托给某个现有 skill 的 workflow
- 典型结构：
  - 说明入口对象
  - 委托同名或非同名 skill
  - 说明停点与下一步

`skill-backed workflow` 可以委托同名 skill，也可以委托不同名 skill；重点是职责清晰，不是名字必须一一对应。

## 2. 核心边界

### 2.1 workflow 只负责什么

`agent workflow` 只允许承载以下内容：

1. 入口语义
2. 对象边界的最小提示
3. 流程阶段顺序
4. 委托关系
5. 停止点
6. 下一步入口建议

例如：

- 可以提示“先去收集 review evidence，再进入 `vibe flow done`”
- 可以说明某个入口是 `skill-backed workflow`
- 但不能在 workflow 内重写 review evidence 的判定规则

### 2.2 workflow 不负责什么

`agent workflow` 不应承载：

1. 长篇业务判断树
2. 具体 shell 修复策略
3. 复杂 blocker 分类
4. 详细 fallback 逻辑
5. 共享状态写入细节
6. 对标准文件的第二套重定义

一句话：

- workflow 只负责编排，不承载复杂业务逻辑
- 例如是否已有 review evidence、何时允许 `vibe flow done`，应由 skill / shell 真源判定

这些内容应分别下沉到：

- `skills/*/SKILL.md`
- `bin/vibe` / `lib/*`
- `docs/standards/*.md`

### 2.3 workflow 与 skill 的关系

必须明确以下几点：

1. 不是每个 workflow 都必须有同名 skill。
2. 只要 workflow 本身仍然是薄入口，它可以：
   - 委托同名 skill
   - 委托不同名 skill
   - 委托 shell 命令组合
   - 充当 alias workflow
3. 只有当 workflow 本身承载了独立业务逻辑时，才需要：
   - 下沉到 skill
   - 或拆成更薄的 workflow

一句话：

- `是否必须有同名 skill` 不是治理标准
- `workflow 是否越界承载业务逻辑` 才是治理标准

## 3. 命名与命名空间

### 3.1 workflow 命名

推荐规则：

- workflow frontmatter `name` 使用 `vibe:*`
- skill `name` 使用 `vibe-*`

这条规则的目标是快速区分层级，而不是强制一一映射。

### 3.2 允许的偏差

以下情况允许短期存在：

- 历史 workflow 还未迁移到 `vibe:*`
- alias workflow 保留历史名字
- slash 入口名与 workflow frontmatter 名不完全一致，但文案必须说明关系

### 3.3 不允许的歧义

以下情况属于高风险歧义：

1. 把 workflow 写成 GitHub workflow
2. 把 workflow 写成 roadmap / feature / release 对象
3. 把 workflow 写成 shell 命令真源
4. 把 `flow`、`workflow`、`worktree` 混成同一概念
5. 在 workflow 中重新定义 `repo issue`、`roadmap item`、`task`、`flow`、`pr`

## 4. 分类规则

每个 `.agent/workflows/*.md` 至少应能被归入以下三类之一：

### A. Skill-backed workflow

判定信号：

- 主要目标是把用户入口委托给 skill
- 结果解释依赖 skill 输出
- workflow 本身不承载复杂判断

### B. Alias workflow

判定信号：

- 只是兼容入口或快捷入口
- 实质上把用户导向已有 workflow / skill / shell 路径
- 不拥有独立真源逻辑

### C. Standalone orchestration workflow

判定信号：

- 本身只做流程编排
- 可以串联多个 workflow / skill / shell
- 但不应承载复杂业务判断

若一个 workflow 无法归入以上任一类，通常说明它语义失控，需要重构。

## 5. 验收标准

检查一个 `agent workflow` 是否合格时，按以下顺序判断：

1. 它是否清楚说明自己是 agent workflow，而不是 GitHub / project workflow？
2. 它是否能被归类为：
   - skill-backed workflow
   - alias workflow
   - standalone orchestration workflow
3. 它是否只保留入口、委托、停点和下一步？
4. 它是否避免重写标准文件中的对象定义？
5. 它是否避免把 shell 能力写成文案假能力？
6. 若它没有同名 skill，这是否能用 alias / orchestration 角色解释？

只要 1-6 都成立，就视为合格。

## 6. 审计输出格式

用本标准审查 `.agent/workflows/` 时，结论至少分成四类：

- `Compliant`
  - 已符合 agent workflow 标准
- `Needs Rename`
  - 主要问题是命名空间或入口名不清
- `Needs Thinning`
  - 主要问题是 workflow 过厚，承载了业务逻辑
- `Needs Reclassification`
  - 主要问题是文件身份不清，需明确它到底是 skill-backed、alias 还是 standalone orchestration

## 7. 变更检查清单

修改或新增 `.agent/workflows/*.md` 时，逐项确认：

1. 是否明确这是 agent workflow，而不是 GitHub / project workflow？
2. 是否说明它属于哪一类 workflow？
3. 是否只保留最小必要对象边界，而没有重写标准定义？
4. 是否把复杂逻辑留在 skill / shell / standard 中？
5. 如果没有同名 skill，是否已能清楚归类为 alias 或 standalone orchestration？
6. 是否避免把 `flow`、`workflow`、`worktree` 混写？
