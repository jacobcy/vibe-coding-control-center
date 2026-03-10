---
document_type: standard
title: Skill Source And Boundary Standard
status: active
scope: skill-governance
authority:
  - skill-source-of-truth
  - runtime-link-boundary
  - shell-skill-boundary
author: GPT-5.4
created: 2026-03-10
last_updated: 2026-03-10
related_docs:
  - SOUL.md
  - CLAUDE.md
  - docs/README.md
  - docs/standards/glossary.md
  - docs/standards/action-verbs.md
  - docs/standards/command-standard.md
  - docs/standards/shell-capability-design.md
  - docs/standards/skill-trigger-standard.md
---

# Vibe Skills 与 Slash 命令标准

本文档只定义 skills、workflows、运行时链接与 shell 管理入口的边界。

本文档**不**定义每个具体 Vibe skill 的应用时机、冲突优先级和自然语言触发矩阵；这些内容以 `docs/standards/skill-trigger-standard.md` 为准。

`Skill 层`、`Shell 能力层`、`workflow` 等正式术语以 [glossary.md](/Users/jacobcy/src/vibe-center/wt-claude-refactor/docs/standards/glossary.md) 为准；本文不重新定义这些术语。

本文档用于解决以下常见混淆：
- `skills/`、`.agent/skills/`、`npx skills`、`vibe skills` 的关系
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

因此：

- skill 可以决定先看哪个 `repo issue`、哪个 roadmap item 进入当前讨论
- workflow 可以编排 `roadmap item -> task -> flow -> pr` 的推进顺序
- skill / workflow 不得把 `flow new` 写成“创建 feature”
- skill / workflow 不得把 roadmap item `type=task` 与本地 task execution record 混成同一实体
- skill / workflow 不得把 `pr`、`flow` 或 `task` 改写成规划层对象

## 1. 概念分层与唯一职责

| 概念 | 作用 | 规范位置 | 管理方式 | 备注 |
|---|---|---|---|---|
| 本项目 Skills 源码 | 团队自有技能定义（权威源） | `skills/<name>/SKILL.md` | Git 维护 | 只改这里，不改运行时镜像 |
| Skills 运行时链接 | 供 Agent 实际加载的 symlink 层 | `.agent/skills/` | `scripts/init.sh` / `vibe skills sync` | 运行时产物，非权威源 |
| 第三方 Markdown Skills 依赖 | 安装/移除外部 skills | 项目级或全局环境 | `npx skills add/remove/ls` | 外部生态依赖管理器 |
| Vibe Skills Shell 工具 | 统一管理 skills 的 Shell 入口 | `bin/vibe skills` -> `lib/skills.sh` | `vibe skills <subcommand>` | Shell 管理入口，不是 skill 内容本身 |
| Vibe Skills 技能 | 对话式审计/推荐流程 | `skills/vibe-skills-manager/SKILL.md` | 由 slash/workflow 触发 | 属于 Skill 层，负责推荐，不直接替代底层 CLI |
| Vibe Skill 治理技能 | 仓库内 `skills/vibe-*` 的创建/审查/漂移治理 | `skills/vibe-skill-audit/SKILL.md` | 由语义匹配或专门入口触发 | 属于 Skill 层，不负责已安装 skills 的清理或同步 |
| OpenSpec OPSX 流程 | OpenSpec 实验流程命令（`/opsx:*`） | `.agent/workflows/opsx-*.md` | `openspec` 工具链 | 独立体系，不归 `npx skills` 管 |
| Claude 插件 | Claude Code 官方插件生态 | `~/.claude/plugins/...` | `claude plugin add ...` | 与 Markdown skills 分离 |
| Slash 命令注册 | 用户输入 `/xxx` 的入口定义 | `.agent/workflows/*.md`（跨 Agent） | 工作流文件维护 | 可加 Claude 适配层 |

## 2. 明确边界（必须遵守）

1. `skills/` 是技能定义的唯一真源（source of truth）。
2. `.agent/skills/` 只做运行时链接，不直接手改业务逻辑。
3. 第三方公共 skills 的安装/卸载使用 `npx skills`。
4. `vibe skills` 是 Shell 能力层中的管理命令；`/vibe-skills-manager` 是 Skill 层中的 workflow 入口，两者不是同一个层级。
5. `vibe-skill-audit` 是仓库内 Vibe 自有 skills 的治理入口；它不等于 `vibe skills`，也不等于 `/vibe-skills-manager`。
6. `opsx-*` 属于 OpenSpec 工作流，生命周期由 `openspec` 管，不并入 `vibe skills` 的安装语义。
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
- 具体 skill 的“什么时候该介入、和邻近 skill 怎么分流”不在本文件展开，统一引用 `docs/standards/skill-trigger-standard.md`。
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
| 同步本项目本地 skills 到运行时 | `vibe skills sync` / `scripts/init.sh` | 手工批量建 symlink |
| 触发 Vibe skills 推荐流程 | `/vibe-skills-manager` -> `skills/vibe-skills-manager/SKILL.md` | 直接把 workflow 写成脚本拼接 |
| 治理仓库内 `skills/vibe-*` | `vibe-skill-audit` / `skills/vibe-skill-audit/SKILL.md` | 让 `/vibe-skills-manager` 兼管 skill 文案设计与审查 |
| 触发 OpenSpec opsx 流程 | `/opsx:*` + `openspec ...` | 通过 `vibe skills` 安装/卸载 |

## 6. 变更检查清单

修改本标准或相关实现时，逐项确认：

1. 是否把 `skills/` 与 `.agent/skills/` 区分为"源码"与"运行时"？
2. 是否明确区分了 `vibe skills`（Shell）与 `/vibe-skills-manager`（Skill workflow）？
3. 是否明确区分了“已安装 skills 管理”与“仓库内 Vibe skill 治理”？
4. 是否把 OpenSpec `opsx-*` 归类到 OpenSpec 工具链而非 skills 依赖管理？
5. 是否对 Claude 采用插件优先策略，并避免用 `npx skills` 代替插件生态？
6. 若引入 `.claude/commands/`，是否保持其为适配层而非第二套业务逻辑？
7. 是否避免在 skill / workflow 文案中重新定义 `repo issue`、`roadmap item`、`task`、`flow`、`pr` 的对象边界？
