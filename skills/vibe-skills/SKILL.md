---
name: vibe-skills
description: Use when skills are messy across IDEs, unsure which are installed globally vs project-level, need to audit/clean/recommend skills, or setting up a new worktree
category: orchestration
trigger: manual
---

# Vibe Skills Manager

AI 驱动的 Skills 生命周期管理。扫描 → 诊断 → 推荐 → 确认 → 执行。
底层操作全部委托给 `npx skills`，AI 负责分析和引导确认。

## When to Use

- Skills 目录混乱，不知道装了什么、装在哪里
- 全局或项目级 skills 数量过多，想清理冗余
- 新 worktree 建好后，想确认 skills 是否完整，并与跨工作区白名单 (`~/.vibe/skills.json`) 同步
- **想要发现新武器时**：不知道当前项目适合安装哪些新 skills，主动要求 AI 根据 `registry.json` 推荐
- **需要说明书时**：想生成/更新一份当前可用 skills 的使用手册（Usage Report）

## 计数排除规则

诊断时以下 skills **不计入总数**，不触发清理建议：

| 类型 | 示例 | 原因 |
|------|------|------|
| **流程 skills** | `openspec-*` 系列 | 工作流体系，非通用能力 |
| **元 skills** | `find-skills`, `skill-creator`, `writing-skills`, `using-superpowers`, `vibe-skills` | 管理 skills 本身的工具 |
| **Antigravity 独立体系** | `~/.gemini/antigravity/skills/` | 独立管理，勿计入全局 |

## 参考上限（建议值，非硬性规定）

| 层级 | 建议上限 | 说明 |
|------|---------|------|
| 全局 | ≤ 10 个 | 排除上表各类后，通用 skills 保持精简 |
| 项目级 | ≤ 20 个 | 排除流程/元 skills 后计算 |

> 超出建议值不强制操作，仅提示用户评估是否有冗余。

## Execution Flow

### Step 1: 扫描现状与上下文收集

1. 取当前环境：
```bash
npx skills ls        # 项目级 skills
npx skills ls -g     # 全局 skills（不含 Antigravity）
cat ~/.vibe/skills.json # 读取跨工作区白名单（如存在）
```
2. **强制确认 IDE 偏好**：即使 AI 从过往记忆或 `~/.vibe/skills.json` 中获取了你的 IDE 偏好（例如 Trae, Antigravity），AI 也**必须向你明示并二次确认**："本次操作是否依然针对这些 IDE 下发生？"，以便后续组合精准的 `--agent` 参数。用户的意图随时会变，绝不能静默代替用户做决定。

### Step 2: 诊断（AI 分析）

读取扫描结果，分三组分析：

**A. 冗余项** — 检查：
- 全局中与本项目无关的 skills（文档处理、特定框架等）
- 项目级中与全局重复安装的通用 skills
- 旧命名 skills（已被更新版本覆盖）
- 超出建议上限的部分（排除流程/元 skills 后计算）

**B. 推荐新增** — AI 对比执行：
这是每次执行 `vibe-skills` 的**必设环节**，除非用户明确跳过：
1. 读取 `skills/vibe-skills/registry.json` 获取官方推荐列表
2. 读取 `CLAUDE.md` 识别当前项目技术栈
3. 对比：找出 `recommended: true` 且当前**未**安装的 skills
4. 按 `project_types` 匹配当前项目类型进行二次筛选

**C. 冷门清理** — 询问用户哪些 skills 很少/从未使用

### Step 3: 分组征询确认

**每组独立确认**，不一次问所有：

```
A. 发现 [N] 个冗余项：
   - [skill-name]: 当前在全局，与项目无关
   是否删除？[y/n]

B. 推荐 [N] 个 skills 适合本项目：
   1. systematic-debugging — 系统性调试方法
   2. writing-plans — 需求转化为实现计划
   安装哪些？[编号/all/跳过]

C. 是否有冷门 skill 需要清理？[y/n]
```

### Step 4: 执行（用户确认后）

**🚨 关键隔离规则 (Claude Code vs 其他 Agent)**：
- **对于纯 Markdown 依赖（如 Trae, Antigravity, Cline）**：统统使用 `npx skills add` 进行分发和安装。
- **对于 Claude Code**：它拥有独立的 MCP Plugin 生态（如 `~/.claude/plugins/installed_plugins.json`）。对于第三方公共包（如 `obra/superpowers`），**禁止使用** `npx skills` 为其强行塞入低级 Markdown，必须提示用户手动使用终端原生命令：`claude plugin add superpowers`。只有我们自己写的、没有发布成插件的本地纯 Markdown 文件（如 `vibe-*`, `openspec-*`），才需要被按需链接进项目的 `.claude/skills/` 中。

**执行命令参考**：
```bash
# 安装到项目（常规 IDE 适配，排除全局向 Claude 推送）
npx skills add obra/superpowers --agent antigravity trae --skill <name> -y

# 全局安装（仅限非 Claude 客户端）
npx skills add obra/superpowers -g --agent antigravity trae --skill <name> -y

# 删除项目级或全局
npx skills remove <name> -y
npx skills remove <name> -g -y
```

### Step 5: 同步跨项目偏好 (`~/.vibe/skills.json`)

如果执行了任何更改，或发现当前项目的必要 skills 尚未写入白名单：
1. 询问用户："是否要将当前项目的有效 skills 单同步到 `~/.vibe/skills.json`，以便未来新 worktree 自动安装？"
2. 如果同意，AI 使用 bash 命令更新 `~/.vibe/skills.json` 这个 JSON 文件。

### Step 6: 生成最终使用报告 (Usage Report) 并持久化

**这是让 skills 真正发挥价值的关键步骤。**
在流程最后，AI 必须基于当前的安装状态，结合 `registry.json` 和项目实际情况，生成一份清晰的 Markdown 报告：
- **按类别分组**（如：工作流、开发规范、项目特定）
- 列出每个 skill 的**一句话使用场景**（When to use & What it does）
- 标注支持的 IDE 范围

**持久化保存：**
必须将这份生成的报告写入到项目文件的 `.agent/skills-handbook.md` 中保存，并给出文件链接供用户随时翻阅。如果是生成跨项目的全局报告，则提议保存至 `~/.vibe/skills-handbook.md`。

## IDE × Agent 名称

| IDE | `--agent` 值 | 生态特性 |
|-----|-------------|----------|
| Claude Code | **不适用 (通过 Plugin)** | 第三方使用原生 Plugin，非第三方才接收 Markdown 链接 |
| Trae | `trae` | 纯 Markdown 驱动 |
| Antigravity | `antigravity` | 纯 Markdown 驱动 |
| Codex | `codex` |
| Kiro | `kiro` |
| 所有 IDE | `*` |

## 用户偏好、Registry 关系与共建讨论

- **`~/.vibe/skills.json`**：存放在用户个人家目录，是当前开发者的**个人偏好白名单**。
- **`registry.json`**：存放在本项目 `skills/vibe-skills/`，是整个 Vibe 团队**推荐的技能标准库**。

**🚨 关键：Registry 的生成与演进必须是“讨论驱动”的**：
1. **非自编自导**：如果项目首次初始化 `registry.json`，AI 绝不能单方面凭借 `CLAUDE.md` 直接生成。AI 必须先抛出**推荐草稿**，与用户讨论："基于识别到的技术栈，我建议将以下 [N] 个工具划为必装推荐，你觉得增删哪些？" 达成共识后才可生成文件。
2. **向外扩展 (Add-to-Registry)**：当用户要求安装一个全新的第三方神器技能时，AI 必须主动发问："这个新技能很好用，是否需要纳入我们的 `registry.json` 成为项目级的团队标准？这需要配置 categories 和 level。" 经过一问一答，再提交 PR 固化知识。

## Common Mistakes

- **不要一次确认所有**：分组询问，用户可以部分确认
- **不要把流程/元 skills 计入总数**：`openspec-*` 和元 skills 排除在外
- **移动 skill 无 move 命令**：需先 `add` 到新位置，再 `remove` 旧位置
- **不要自动执行**：所有操作必须用户确认后才执行
