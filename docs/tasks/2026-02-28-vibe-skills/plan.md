# vibe-skills Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 创建 `skills/vibe-skills/` skill，让 AI 通过对话驱动 Skills 生命周期管理——扫描、诊断、推荐、确认、执行，底层操作全部委托给 `npx skills`。

**Architecture:** SKILL.md 定义 AI 对话流程（触发 → 扫描 → 诊断 → 推荐 → 确认 → 执行）；`registry.json` 存储 skills 推荐数据库；`npx skills ls/add/remove` 承担所有实际操作，AI 不写自定义脚本。

**Tech Stack:** Zsh skill framework, `npx skills` CLI, JSON (registry), `~/.vibe/skills.json` (user prefs)

---

### Task 1: 创建 registry.json

**Files:**
- Create: `skills/vibe-skills/registry.json`

**Step 1: 创建文件**

```json
{
  "_comment": "vibe-skills 推荐注册表。AI 读取此文件推荐适合当前项目的 skills。",
  "_schema": "name=skill唯一名, source=npx安装包, level=global|project|either, ides=适用IDE列表, category=分类, project_types=适用项目类型, recommended=是否默认推荐",
  "skills": [
    {
      "name": "systematic-debugging",
      "source": "obra/superpowers",
      "level": "project",
      "ides": ["all"],
      "category": "development-workflow",
      "project_types": ["any"],
      "recommended": true,
      "description": "系统性调试方法，遇到 bug 必备"
    },
    {
      "name": "brainstorming",
      "source": "obra/superpowers",
      "level": "global",
      "ides": ["all"],
      "category": "development-workflow",
      "project_types": ["any"],
      "recommended": true,
      "description": "需求探索和功能设计，任何项目起点"
    },
    {
      "name": "verification-before-completion",
      "source": "obra/superpowers",
      "level": "global",
      "ides": ["all"],
      "category": "discipline",
      "project_types": ["any"],
      "recommended": true,
      "description": "完成前验证，防止草率声称完成"
    },
    {
      "name": "writing-skills",
      "source": "obra/superpowers",
      "level": "global",
      "ides": ["all"],
      "category": "meta",
      "project_types": ["any"],
      "recommended": true,
      "description": "创建新 skill 的方法论"
    },
    {
      "name": "test-driven-development",
      "source": "obra/superpowers",
      "level": "global",
      "ides": ["all"],
      "category": "discipline",
      "project_types": ["any"],
      "recommended": true,
      "description": "TDD 工作流，适合任何项目"
    },
    {
      "name": "using-git-worktrees",
      "source": "obra/superpowers",
      "level": "global",
      "ides": ["all"],
      "category": "workflow",
      "project_types": ["any"],
      "recommended": true,
      "description": "Git worktree 隔离开发，多任务并行"
    },
    {
      "name": "executing-plans",
      "source": "obra/superpowers",
      "level": "project",
      "ides": ["all"],
      "category": "orchestration",
      "project_types": ["any"],
      "recommended": true,
      "description": "按计划执行任务，带检查点"
    },
    {
      "name": "writing-plans",
      "source": "obra/superpowers",
      "level": "project",
      "ides": ["all"],
      "category": "orchestration",
      "project_types": ["any"],
      "recommended": true,
      "description": "将需求转化为详细实现计划"
    },
    {
      "name": "finishing-a-development-branch",
      "source": "obra/superpowers",
      "level": "project",
      "ides": ["all"],
      "category": "workflow",
      "project_types": ["any"],
      "recommended": true,
      "description": "完成开发分支：merge/PR/cleanup 决策"
    },
    {
      "name": "receiving-code-review",
      "source": "obra/superpowers",
      "level": "project",
      "ides": ["all"],
      "category": "process",
      "project_types": ["any"],
      "recommended": true,
      "description": "处理 Code Review 反馈，辨别有效建议"
    },
    {
      "name": "requesting-code-review",
      "source": "obra/superpowers",
      "level": "project",
      "ides": ["all"],
      "category": "process",
      "project_types": ["any"],
      "recommended": true,
      "description": "发起 Code Review 前的准备和自检"
    },
    {
      "name": "dispatching-parallel-agents",
      "source": "obra/superpowers",
      "level": "project",
      "ides": ["all"],
      "category": "orchestration",
      "project_types": ["any"],
      "recommended": true,
      "description": "并行调度多个子 Agent 执行独立任务"
    },
    {
      "name": "subagent-driven-development",
      "source": "obra/superpowers",
      "level": "project",
      "ides": ["all"],
      "category": "orchestration",
      "project_types": ["any"],
      "recommended": true,
      "description": "子 Agent 驱动的开发执行模式"
    },
    {
      "name": "web-design-guidelines",
      "source": "obra/superpowers",
      "level": "project",
      "ides": ["all"],
      "category": "design",
      "project_types": ["web", "nextjs"],
      "recommended": false,
      "description": "Web 设计规范，适合前端项目"
    }
  ]
}
```

**Step 2: 验证 JSON 格式**

```bash
jq . skills/vibe-skills/registry.json
```

预期输出：格式化后的 JSON，无报错。

**Step 3: Commit**

```bash
git add skills/vibe-skills/registry.json
git commit -m "feat(vibe-skills): add skills registry.json with 14 recommended skills"
```

---

### Task 2: 创建 SKILL.md

**Files:**
- Create: `skills/vibe-skills/SKILL.md`

**Step 1: 创建文件**

内容见下方完整 SKILL.md（注意 CSO 描述格式遵循 `writing-skills` 规范）：

```markdown
---
name: vibe-skills
description: Use when skills are messy, unknown which are installed globally vs project-level, need to audit/clean/install skills across IDEs, or want recommendations for current project
category: orchestration
trigger: manual
---

# Vibe Skills Manager

AI 驱动的 Skills 生命周期管理。扫描 → 诊断 → 推荐 → 确认 → 执行。
底层操作全部委托给 `npx skills`，AI 负责分析和引导。

## When to Use

- Skills 目录混乱，不知道装了什么
- 全局 skills 超过 10 个或项目超过 20 个
- 新 worktree 需要确认 skills 是否完整
- 想知道当前项目适合安装哪些 skills

## Execution Flow

### Step 1: 扫描现状

```bash
npx skills ls          # 项目级 skills
npx skills ls -g       # 全局 skills
```

### Step 2: 诊断（AI 执行）

读取扫描结果，分三组分析：

**A. 违规项** — 检查以下条件：
- 全局 skills > 10 个（Antigravity 独立不计）
- 项目 skills > 20 个
- 明显应该全局却在项目级的 skills（如 `brainstorming`, `writing-skills`）
- 明显应该项目级却在全局的 skills（如业务特定 skills）

**B. 推荐新增** — AI 执行：
1. 读取 `skills/vibe-skills/registry.json`
2. 读取 `CLAUDE.md` 识别项目技术栈
3. 过滤出 `recommended: true` 且未安装的 skills
4. 按 `project_types` 匹配当前项目类型

**C. 冷门清理** — 询问用户哪些 skills 从未用过

### Step 3: 分组征询确认

每组独立确认，不一次询问所有：

```
A. 发现 [N] 个违规项，建议移动/删除：
   - [skill-name]: 当前在全局，建议移至项目级
   是否修复？[y/n/详细]

B. 推荐 [N] 个 skills 适合本项目：
   1. systematic-debugging — 系统性调试方法
   2. writing-plans — 将需求转化为实现计划
   安装哪些？[输入编号/all/skip]

C. 是否有冷门 skill 需要清理？[y/n]
```

### Step 4: 执行（用户确认后）

根据用户选择执行对应命令：

```bash
# 安装到项目（所有适配 IDE）
npx skills add obra/superpowers --agent antigravity trae --skill <name> -y

# 安装全局
npx skills add obra/superpowers -g --agent antigravity trae --skill <name> -y

# 删除项目级
npx skills remove <name>

# 删除全局
npx skills remove <name> -g
```

## IDE × Agent 名称映射

| IDE | `--agent` 值 |
|-----|-------------|
| Claude Code | `claude-code` |
| Trae | `trae` |
| Antigravity | `antigravity` |
| Codex | `codex` |
| Kiro | `kiro` |
| Superpowers (共享) | `*` |

## 限额策略

| 层级 | 限额 | 说明 |
|------|------|------|
| 全局 | ≤ 10 个 | Antigravity 独立体系，不计入 |
| 项目级 | ≤ 20 个 | 含 symlinks |

## 用户偏好文件

`~/.vibe/skills.json` — 用户认可的 skills 白名单，新建 worktree 时由 `install.sh` 自动安装。
如需更新白名单，直接编辑此文件。

## Common Mistakes

- **不要一次确认所有操作**：分组，用户可以部分确认
- **Antigravity 全局不受限額管控**：其 skills 独立管理
- **移动 skill 不是 add+remove**：`npx skills` 无 move 命令，需先 add 到新位置再 remove 旧位置
```

**Step 2: 验证字数**

```bash
wc -w skills/vibe-skills/SKILL.md
```

预期：< 500 words（skill 质量要求）

**Step 3: Commit**

```bash
git add skills/vibe-skills/SKILL.md
git commit -m "feat(vibe-skills): add SKILL.md with full conversation flow"
```

---

### Task 3: 添加 symlink 分发到 install.sh

**Files:**
- Modify: `install.sh:23-30`（现有 vibe-* symlink 循环段）

**Step 1: 确认当前 symlink 逻辑已覆盖 vibe-skills**

```bash
grep -n "vibe-\*" install.sh
```

预期输出：`for skill in skills/vibe-*/;` — `vibe-skills` 会被这个 glob 自动包含，**无需修改**。

**Step 2: 验证 symlink 创建正确**

```bash
bash install.sh 2>&1 | head -20
ls -la .agent/skills/vibe-skills
ls -la .trae/skills/vibe-skills
```

预期：显示 symlink 指向 `../../skills/vibe-skills`

**Step 3: Commit（仅当 install.sh 有变动时）**

```bash
git add install.sh
git commit -m "feat(install): include vibe-skills in symlink distribution"
```

---

### Task 4: 更新 task README（推进 gate 状态）

**Files:**
- Modify: `docs/tasks/2026-02-28-vibe-skills/README.md`

**Step 1: 更新 gates 状态**

将 `spec`、`plan`、`code` 的 gate 状态更新为 `passed`，`current_layer` 改为 `test`。

**Step 2: Commit**

```bash
git add docs/tasks/2026-02-28-vibe-skills/README.md
git commit -m "docs(tasks): update vibe-skills gates — spec/plan/code passed"
```

---

### Task 5: 验证（Test Gate）

**Step 1: 验证文件存在**

```bash
ls skills/vibe-skills/
# 预期：SKILL.md  registry.json
```

**Step 2: 验证 registry.json 可用**

```bash
jq '.skills | length' skills/vibe-skills/registry.json
# 预期：14

jq '.skills[] | select(.recommended == true) | .name' skills/vibe-skills/registry.json
# 预期：列出 13 个 recommended skills
```

**Step 3: 验证 symlink**

```bash
ls -la .agent/skills/vibe-skills
# 预期：lrwxr-xr-x -> ../../skills/vibe-skills

ls -la .trae/skills/vibe-skills
# 预期：lrwxr-xr-x -> ../../skills/vibe-skills
```

**Step 4: 验证 SKILL.md 格式**

```bash
head -6 skills/vibe-skills/SKILL.md
# 预期：frontmatter 含 name, description, category, trigger

wc -w skills/vibe-skills/SKILL.md
# 预期：< 600 words
```

**Step 5: Commit**

```bash
git add .
git commit -m "test(vibe-skills): verify all artifacts correct"
```
