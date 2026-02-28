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
- 新 worktree 建好后，想确认 skills 是否完整
- 想知道当前项目适合安装哪些 skills

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

### Step 1: 扫描现状

```bash
npx skills ls        # 项目级 skills
npx skills ls -g     # 全局 skills（不含 Antigravity）
```

### Step 2: 诊断（AI 分析）

读取扫描结果，分三组分析：

**A. 冗余项** — 检查：
- 全局中与本项目无关的 skills（文档处理、特定框架等）
- 项目级中与全局重复安装的通用 skills
- 旧命名 skills（已被更新版本覆盖）
- 超出建议上限的部分（排除流程/元 skills 后计算）

**B. 推荐新增** — AI 执行：
1. 读取 `skills/vibe-skills/registry.json` 获取推荐列表
2. 读取 `CLAUDE.md` 识别项目技术栈
3. 过滤出 `recommended: true` 且当前未安装的 skills
4. 按 `project_types` 匹配当前项目类型筛选

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

```bash
# 安装到项目（适配 IDE）
npx skills add obra/superpowers --agent antigravity trae --skill <name> -y

# 全局安装
npx skills add obra/superpowers -g --agent antigravity trae --skill <name> -y

# 删除项目级
npx skills remove <name> -y

# 删除全局
npx skills remove <name> -g -y
```

## IDE × Agent 名称

| IDE | `--agent` 值 |
|-----|-------------|
| Claude Code | `claude-code` |
| Trae | `trae` |
| Antigravity | `antigravity` |
| Codex | `codex` |
| Kiro | `kiro` |
| 所有 IDE | `*` |

## 用户偏好

`~/.vibe/skills.json` — 用户认可的 skills 白名单，新建 worktree 时由 `install.sh` 自动安装。
修改白名单：直接编辑此文件，下次 `vibe flow start` 时生效。

## Common Mistakes

- **不要一次确认所有**：分组询问，用户可以部分确认
- **不要把流程/元 skills 计入总数**：`openspec-*` 和元 skills 排除在外
- **移动 skill 无 move 命令**：需先 `add` 到新位置，再 `remove` 旧位置
- **不要自动执行**：所有操作必须用户确认后才执行
