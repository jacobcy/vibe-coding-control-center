# Vibe Skills 与 Slash 命令标准

本文档只定义 skills、workflows、运行时链接与 shell 管理入口的边界。

`Skill 层`、`Shell 能力层`、`workflow` 等正式术语以 [glossary.md](/Users/jacobcy/src/vibe-center/wt-claude-refactor/docs/standards/glossary.md) 为准；本文不重新定义这些术语。

本文档用于解决以下常见混淆：
- `skills/`、`.agent/skills/`、`npx skills`、`vibe skills` 的关系
- OpenSpec 的 `opsx-*` 流程和 Vibe Skills 的边界
- 跨 Agent 工作流注册（`.agent/workflows/`）与 Claude 专用命令注册（`.claude/commands/`）的选择

## 1. 概念分层与唯一职责

| 概念 | 作用 | 规范位置 | 管理方式 | 备注 |
|---|---|---|---|---|
| 本项目 Skills 源码 | 团队自有技能定义（权威源） | `skills/<name>/SKILL.md` | Git 维护 | 只改这里，不改运行时镜像 |
| Skills 运行时链接 | 供 Agent 实际加载的 symlink 层 | `.agent/skills/` | `scripts/init.sh` / `vibe skills sync` | 运行时产物，非权威源 |
| 第三方 Markdown Skills 依赖 | 安装/移除外部 skills | 项目级或全局环境 | `npx skills add/remove/ls` | 外部生态依赖管理器 |
| Vibe Skills Shell 工具 | 统一管理 skills 的 Shell 入口 | `bin/vibe skills` -> `lib/skills.sh` | `vibe skills <subcommand>` | Shell 管理入口，不是 skill 内容本身 |
| Vibe Skills 技能 | 对话式审计/推荐流程 | `skills/vibe-skills/SKILL.md` | 由 slash/workflow 触发 | 属于 Skill 层，负责推荐，不直接替代底层 CLI |
| OpenSpec OPSX 流程 | OpenSpec 实验流程命令（`/opsx:*`） | `.agent/workflows/opsx-*.md` | `openspec` 工具链 | 独立体系，不归 `npx skills` 管 |
| Claude 插件 | Claude Code 官方插件生态 | `~/.claude/plugins/...` | `claude plugin add ...` | 与 Markdown skills 分离 |
| Slash 命令注册 | 用户输入 `/xxx` 的入口定义 | `.agent/workflows/*.md`（跨 Agent） | 工作流文件维护 | 可加 Claude 适配层 |

## 2. 明确边界（必须遵守）

1. `skills/` 是技能定义的唯一真源（source of truth）。
2. `.agent/skills/` 只做运行时链接，不直接手改业务逻辑。
3. 第三方公共 skills 的安装/卸载使用 `npx skills`。
4. `vibe skills` 是 Shell 能力层中的管理命令；`/vibe-skills` 是 Skill 层中的 workflow 入口，两者不是同一个层级。
5. `opsx-*` 属于 OpenSpec 工作流，生命周期由 `openspec` 管，不并入 `vibe skills` 的安装语义。
6. Claude 第三方能力优先走 plugin 机制（例如 `everything-claude-code`、`superpowers`），不要用 `npx skills` 去模拟插件。
7. slash / workflow 只能调度既有 GitHub 对象与本地 execution record，不得在入口文案中重新定义 `repo issue`、`roadmap item`、`task`、`flow`。

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
- Frontmatter：`name`, `description`, `user-invokable`（按需）
- `Overview`
- `When to Use`
- `Execution Flow` 或等价步骤说明
- `Guardrails` / `Common Mistakes`（边界）

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
| 触发 Vibe skills 推荐流程 | `/vibe-skills` -> `skills/vibe-skills/SKILL.md` | 直接把 workflow 写成脚本拼接 |
| 触发 OpenSpec opsx 流程 | `/opsx:*` + `openspec ...` | 通过 `vibe skills` 安装/卸载 |

## 6. Slash / Workflow 边界

slash 与 workflow 入口只负责调度、编排与提示，不定义共享状态对象模型。

统一约束：

- `/vibe-new-feature` 面向“选择或创建规划目标”的入口文案，但底层对象仍应落到 `repo issue` / `roadmap item`
- `/vibe-new-flow` 只创建执行现场，不得把 `flow` 说成 feature 本体
- `/vibe-issue` 只处理 `repo issue` 生命周期与关联建议，不创建 execution record 语义
- `/vibe-task` 只围绕本地 execution record 调度，不承担 GitHub Project 规划职责
- `/vibe-save` 只保存上下文与执行事实，不得回写新的规划对象定义
- workflow 可以建议或填写 `spec_standard` / `spec_ref`，但不得重写 GitHub item 的官方字段

禁止：

- 在 slash 文案里把 `task` 与 roadmap item `type=task` 混用
- 在 workflow 入口里把 `flow` 说成规划入口
- 绕过 Shell 能力层直接重定义 GitHub Project 对象链路
- 把 `openspec` / `kiro` / `superpowers` / `supervisor` 写成 GitHub 官方 item 来源类型

## 7. 变更检查清单

修改本标准或相关实现时，逐项确认：

1. 是否把 `skills/` 与 `.agent/skills/` 区分为"源码"与"运行时"？
2. 是否明确区分了 `vibe skills`（Shell）与 `/vibe-skills`（Skill workflow）？
3. 是否把 OpenSpec `opsx-*` 归类到 OpenSpec 工具链而非 skills 依赖管理？
4. 是否对 Claude 采用插件优先策略，并避免用 `npx skills` 代替插件生态？
5. 若引入 `.claude/commands/`，是否保持其为适配层而非第二套业务逻辑？
6. 是否避免在 slash / workflow 文案中重新发明 `repo issue -> roadmap item -> task -> flow -> PR` 这条对象链？
