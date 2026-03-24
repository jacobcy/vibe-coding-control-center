---
document_type: standard
title: Skill Source And Boundary Standard
status: active
scope: skill-governance
authority:
  - skill-source-of-truth
  - runtime-link-boundary
  - python-skill-boundary
author: GPT-5.4
created: 2026-03-10
last_updated: 2026-03-24
related_docs:
  - SOUL.md
  - CLAUDE.md
  - docs/README.md
  - docs/references/skill-loop-memo.md
  - docs/standards/glossary.md
  - docs/standards/action-verbs.md
  - docs/standards/v3/command-standard.md
  - docs/standards/v3/python-capability-design.md
  - docs/standards/v3/skill-trigger-standard.md
---

# Vibe Skills 与 Slash 命令标准

本文档只定义 skills、workflows、运行时链接与 Python CLI 管理入口的边界。

本文档**不**定义每个具体 Vibe skill 的应用时机、冲突优先级和自然语言触发矩阵；这些内容以 `docs/standards/v3/skill-trigger-standard.md` 为准。

`Skill 层`、`Python 能力层`、`workflow` 等正式术语以 [glossary.md](/Users/jacobcy/src/vibe-center/wt-claude-refactor/docs/standards/glossary.md) 为准；本文不重新定义这些术语。

本文档用于解决以下常见混淆：
- `skills/`、`.agent/skills/`、`npx skills`、`vibe3 skills` 的关系
- OpenSpec 的 `opsx-*` 流程和 Vibe Skills 的边界
- 跨 Agent 工作流注册（`.agent/workflows/`）与 Claude 专用命令注册（`.claude/commands/`）的选择

## 0. 对象模型边界

skills / workflows 可以调度对象，但不得重新定义对象模型。

固定边界如下：

- `repo issue` 是来源层对象
- `roadmap item` 是 mirrored GitHub Project item
- `task` 是 execution record
- `flow` 是运行时现场
- `pr` 是交付与审查单元
- `task issue` 是某个 `task` 的主闭环 `repo issue` 角色；若显式落地，则字段为 `primary_issue_ref`

因此：

- skill 可以决定先看哪个 `repo issue`、哪个 roadmap item 进入当前讨论
- workflow 可以编排用户主链 `repo issue -> flow -> plan/spec -> commit -> pr -> done`
- workflow 也可以在内部编排 `roadmap item -> task -> flow` 作为桥接链
- skill / workflow 可以读取多个 `issue_refs`，但只有 `primary_issue_ref` 对应的那个 `repo issue` 才应被写成 `task issue`
- skill / workflow 不得把 `flow new` 写成"创建 feature"
- skill / workflow 不得把 roadmap item `type=task` 与本地 task execution record 混成同一实体
- skill / workflow 不得把 `pr`、`flow` 或 `task` 改写成规划层对象
- skill / workflow 不得把 roadmap mirror / cache 缺失写成 execution 无法启动的默认根因

## 0.1 Slash / Workflow Boundary

slash 与 workflow 入口只负责调度、编排与提示，不定义共享状态对象模型。

统一约束：

- `/vibe-new-feature` 面向"选择或创建规划目标"的入口文案，但底层对象仍应落到 `repo issue` / roadmap item
- `/vibe-new-flow` 只创建执行现场，不得把 `flow` 说成 feature 本体
- `/vibe-issue` 只处理 `repo issue` 生命周期与关联建议，不创建 execution record 语义
- `/vibe-task` 只围绕本地 execution record 调度，不承担 GitHub Project 规划职责
- `/vibe-save` 只保存上下文与执行事实，不得回写新的规划对象定义
- workflow 可以建议或填写 `spec_standard` / `spec_ref`，但不得重写 GitHub item 的官方字段

禁止：

- 在 slash 文案里把 `task` 与 roadmap item `type=task` 混用
- 在 workflow 入口里把 `flow` 说成规划入口
- 绕过 Python 能力层直接重定义 GitHub Project 对象链路
- 把 `openspec` / `kiro` / `superpowers` / `supervisor` 写成 GitHub 官方 item 来源类型

## 0.2 核心 Skill 结构速记

下面这张表只做结构速记，不取代各 skill 的正式定义。

正式触发与分流以 `docs/standards/v3/skill-trigger-standard.md` 为准；个人查看用备忘见 `docs/references/skill-loop-memo.md`。

用户主链固定为：`vibe-issue -> vibe-new -> vibe-start -> spec execution -> vibe-commit -> vibe-integrate -> vibe-done`。

内部桥接链保留为：`vibe-issue -> vibe-roadmap -> vibe-new -> vibe-start`。

边界固定为：

- `vibe-new` 负责旧 flow 到新 flow 的转换，不创建 task，也不直接进入执行
- `vibe-start` 负责从 issue 落 task，再把 execution spec 交给对应执行体系
- `vibe-start` / `vibe-commit` / `vibe-integrate` / `vibe-done` 若需要判断 task 的主闭环 issue，应优先读取 `primary_issue_ref`
- `vibe-task` 是 task-centered audit
- `vibe-check` 是 runtime / recovery audit

| 区段 | Skill | 主要职责 | 明确不负责 |
|---|---|---|---|
| 来源层 | `vibe-issue` | GitHub `repo issue` 的创建、查重、模板补全、标签与创建前治理 | roadmap 排期、task 创建、runtime 修复 |
| 规划层 | `vibe-roadmap` | roadmap item / 版本窗口 / triage / "下一个 roadmap 做什么" | Issue 创建、task-flow runtime 修复 |
| 规划入口 | `vibe-new` | 决定主 issue、完成旧 flow 到新 flow 的转换，并决定是否携带未提交改动进入新 flow | 创建 task、直接进入执行 |
| 执行入口 | `vibe-start` | 从 issue 落 task，并把 execution spec 交给对应执行体系 | 创建 issue、承担旧 flow 到新 flow 的转换 |
| 发布层 | `vibe-commit` | commit 分组、PR 切片、发 PR | merge、close task、close issue、close flow |
| 整合层 | `vibe-integrate` | review、CI、merge readiness、stack 顺序 | task/issue 真源写入 |
| 收口层 | `vibe-done` | merge 后或 review-ready 后的最终收口编排 | 新目标 intake、业务代码修复 |
| 审计旁路 | `vibe-task` | task registry、`roadmap <-> task` 映射、task 总览与数据质量审计 | runtime `task <-> flow` 修复 |
| 审计旁路 | `vibe-check` | `task <-> flow` / worktree runtime / stale binding 审计与修复 | roadmap 排期、registry/roadmap-task 语义审计 |

## 1. 概念分层与唯一职责

| 概念 | 作用 | 规范位置 | 管理方式 | 备注 |
|---|---|---|---|---|
| 本项目 Skills 源码 | 团队自有技能定义（权威源） | `skills/<name>/SKILL.md` | Git 维护 | 只改这里，不改运行时镜像 |
| Skills 运行时链接 | 供 Agent 实际加载的 symlink 层 | `.agent/skills/` | `scripts/init.sh` / `vibe3 skills sync` | 运行时产物，非权威源 |
| 第三方 Markdown Skills 依赖 | 安装/移除外部 skills | 项目级或全局环境 | `npx skills add/remove/ls` | 外部生态依赖管理器 |
| Vibe Skills Python 工具 | 统一管理 skills 的 Python 入口 | `vibe3 skills` -> `src/vibe3/commands/skills.py` | `vibe3 skills <subcommand>` | Python 管理入口，不是 skill 内容本身 |
| Vibe Skills 技能 | 对话式审计/推荐流程 | `skills/vibe-skills-manager/SKILL.md` | 由 slash/workflow 触发 | 属于 Skill 层，负责推荐，不直接替代底层 CLI |
| Vibe Skill 治理技能 | 仓库内 `skills/vibe-*` 的创建/审查/漂移治理 | `skills/vibe-skill-audit/SKILL.md` | 由语义匹配或专门入口触发 | 属于 Skill 层，不负责已安装 skills 的清理或同步 |
| OpenSpec OPSX 流程 | OpenSpec 实验流程命令（`/opsx:*`） | `.agent/workflows/opsx-*.md` | `openspec` 工具链 | 独立体系，不归 `npx skills` 管 |
| Claude 插件 | Claude Code 官方插件生态 | `~/.claude/plugins/...` | `claude plugin add ...` | 与 Markdown skills 分离 |
| Slash 命令注册 | 用户输入 `/xxx` 的入口定义 | `.agent/workflows/*.md`（跨 Agent） | 工作流文件维护 | 可加 Claude 适配层 |

## 2. 明确边界（必须遵守）

1. `skills/` 是技能定义的唯一真源（source of truth）。
2. `.agent/skills/` 只做运行时链接，不直接手改业务逻辑。
3. 第三方公共 skills 的安装/卸载使用 `npx skills`。
4. `vibe3 skills` 是 Python 能力层中的管理命令；`/vibe-skills-manager` 是 Skill 层中的 workflow 入口，两者不是同一个层级。
5. `vibe-skill-audit` 是仓库内 Vibe 自有 skills 的治理入口；它不等于 `vibe3 skills`，也不等于 `/vibe-skills-manager`。
6. `opsx-*` 属于 OpenSpec 工作流，生命周期由 `openspec` 管，不并入 `vibe3 skills` 的安装语义。
7. Claude 第三方能力优先走 plugin 机制（例如 `everything-claude-code`、`superpowers`），不要用 `npx skills` 去模拟插件。

为避免编号漂移，本节要求应视为 1-7 的约束集合；如后续新增条目，必须同步更新检查清单。

## 3. 关于 `.agent/workflows` vs `.claude/commands`

结论：两者都可以用，但职责应分离，避免双真源。

推荐策略：
1. 继续把 `.agent/workflows/` 作为跨 Agent 的权威命令语义层。
2. 在 Claude Code 中可以增加 `.claude/commands/` 作为 Claude 专用注册层（适配层）。
3. `.claude/commands/*` 只做薄封装，内容应委托到 `.agent/workflows/*` 或 `skills/*`，不要复制完整逻辑。
4. 若两处内容冲突，以 `.agent/workflows/` 为准并及时同步。

一句话：
`.agent/workflows/` 管"语义与流程"，`.claude/commands/` 管"Claude 入口适配"。

## 4. SKILL.md 最小规范

每个自有 skill 至少包含：
- Frontmatter：`name`, `description`, `user-invocable`（按需）
- `Overview`
- `When to Use`
- `Execution Flow` 或等价步骤说明
- `Guardrails` / `Common Mistakes`（边界）

补充要求：

- `description` 只定义触发条件，不摘要整个流程。
- 具体 skill 的"什么时候该介入、和邻近 skill 怎么分流"不在本文件展开，统一引用 `docs/standards/v3/skill-trigger-standard.md`。
- 若某个 skill 是高频路由入口，正文应优先保持轻量，把长篇交互模板或审计样例下沉到 `references/`。

建议目录结构：

```text
skills/<name>/
  SKILL.md          # 必须
  README.md         # 可选
  examples/         # 可选
```

## 5. 操作映射（避免概念串线）

| 目标 | 正确入口 | 不该使用 |
|---|---|---|
| 安装 Claude 插件（如 superpowers） | `claude plugin add <plugin>` | `npx skills add` |
| 管理第三方 Markdown skills | `npx skills add/remove/ls` | 手工改 `.agent/skills/` |
| 同步本项目本地 skills 到运行时 | `vibe3 skills sync` / `scripts/init.sh` | 手工批量建 symlink |
| 触发 Vibe skills 推荐流程 | `/vibe-skills-manager` -> `skills/vibe-skills-manager/SKILL.md` | 直接把 workflow 写成脚本拼接 |
| 治理仓库内 `skills/vibe-*` | `vibe-skill-audit` / `skills/vibe-skill-audit/SKILL.md` | 让 `/vibe-skills-manager` 兼管 skill 文案设计与审查 |
| 触发 OpenSpec opsx 流程 | `/opsx:*` + `openspec ...` | 通过 `vibe3 skills` 安装/卸载 |

## 6. 变更检查清单

修改本标准或相关实现时，逐项确认：

1. 是否把 `skills/` 与 `.agent/skills/` 区分为"源码"与"运行时"？
2. 是否明确区分了 `vibe3 skills`（Python CLI）与 `/vibe-skills-manager`（Skill workflow）？
3. 是否明确区分了"已安装 skills 管理"与"仓库内 Vibe skill 治理"？
4. 是否把 OpenSpec `opsx-*` 归类到 OpenSpec 工具链而非 skills 依赖管理？
5. 是否对 Claude 采用插件优先策略，并避免用 `npx skills` 代替插件生态？
6. 若引入 `.claude/commands/`，是否保持其为适配层而非第二套业务逻辑？
7. 是否避免在 skill / workflow 文案中重新定义 `repo issue`、`roadmap item`、`task`、`flow`、`pr` 的对象边界？

(End of file - total 196 lines)
