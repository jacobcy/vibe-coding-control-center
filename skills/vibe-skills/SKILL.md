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
- 全局 skills 超过 10 个或项目级超过 20 个
- 新 worktree 建好后，想确认 skills 是否完整
- 想知道当前项目适合安装哪些 skills

## Execution Flow

### Step 1: 扫描现状

执行以下命令获取当前 skills 清单：

```bash
npx skills ls        # 项目级 skills
npx skills ls -g     # 全局 skills（不含 Antigravity）
```

### Step 2: 诊断（AI 分析）

读取扫描结果，分三组分析：

**A. 违规项** — 检查：
- 全局 skills > 10 个（Antigravity `~/.gemini/antigravity/skills/` 独立，不计入）
- 项目 skills > 20 个
- 应在全局却在项目的 skills（如 `brainstorming`, `writing-skills`, `test-driven-development`）
- 应在项目却在全局的 skills（业务特定 skills）

**B. 推荐新增** — AI 执行：
1. 读取 `skills/vibe-skills/registry.json` 获取推荐列表
2. 读取 `CLAUDE.md` 识别项目技术栈
3. 过滤出 `recommended: true` 且当前未安装的 skills
4. 按 `project_types` 匹配当前项目类型筛选

**C. 冷门清理** — 询问用户哪些 skills 很少/从未使用

### Step 3: 分组征询确认

**每组独立确认**，不一次问所有：

```
A. 发现 [N] 个问题：
   - [skill-name]: 当前在全局，建议移至项目级
   是否修复？[y/n]

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

## 限额策略

| 层级 | 限额 | 检测命令 |
|------|------|---------|
| 全局 | ≤ 10 个 | `npx skills ls -g` |
| 项目级 | ≤ 20 个 | `npx skills ls` |

> **Antigravity 例外**: `~/.gemini/antigravity/skills/` 独立管理，不计入全局限额。

## 用户偏好

`~/.vibe/skills.json` — 用户认可的 skills 白名单，新建 worktree 时由 `install.sh` 自动安装。
修改白名单：直接编辑此文件，下次 `vibe flow start` 时生效。

## Common Mistakes

- **不要一次确认所有**：分组询问，用户可以部分确认
- **移动 skill 无 move 命令**：需先 `add` 到新位置，再 `remove` 旧位置
- **不要自动执行**：所有操作必须用户确认后才执行
