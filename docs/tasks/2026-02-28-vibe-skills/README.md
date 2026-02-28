---
task_id: 2026-02-28-vibe-skills
document_type: task-readme
title: vibe-skills — Skills 生命周期管理 Skill
current_layer: prd
status: in-progress
author: Claude Sonnet 4
created: 2026-02-28
last_updated: 2026-02-28
related_docs:
  - CLAUDE.md
  - skills/vibe-audit/SKILL.md
  - .agents/skills/writing-skills/SKILL.md
  - docs/standards/doc-quality-standards.md
gates:
  scope:
    status: passed
    timestamp: "2026-02-28T21:55:00+08:00"
    reason: 需求通过 brainstorming 完整探讨，确认方向；发现 npx skills 已覆盖所有操作，设计大幅精简，无需自写脚本
  spec:
    status: pending
    timestamp: ""
    reason: ""
  plan:
    status: pending
    timestamp: ""
    reason: ""
  test:
    status: pending
    timestamp: ""
    reason: ""
  code:
    status: pending
    timestamp: ""
    reason: ""
  audit:
    status: pending
    timestamp: ""
    reason: ""
---

# vibe-skills — Skills 生命周期管理 Skill

## 1. 背景 & 问题

系统中安装了 7 种 AI 工具（Claude Code、Trae、Antigravity、Kiro、Codex、Copilot、Superpowers），每种工具有独立的 skills 目录，导致：

- **层级混乱**：项目级 skills 泄漏到全局（如 `vibe-boundary-check` 出现在 `~/.agents/skills/`）
- **数量失控**：Antigravity 全局 930+ skills，其他 IDE 无明确限额
- **跨工具冗余**：同一 skill 在多个 IDE 目录重复，缺乏统一视图
- **冷热不知**：不清楚哪些 skills 常用、哪些从未被调用
- **推荐盲目**：新项目不知道该安装哪些 skills，适合哪些 IDE

## 2. 关键发现：`npx skills` 已具备所有操作能力

```
skills ls                    → 列出项目级 skills（扫描）
skills ls -g                 → 列出全局 skills
skills ls -a claude-code     → 按 IDE 过滤
skills add <pkg> -g          → 全局安装
skills add <pkg> --agent *   → 安装到所有 IDE
skills remove <name> -g      → 全局删除
skills remove <name>         → 项目级删除
skills find <query>          → 搜索可用 skills
skills check / update        → 更新管理
```

**设计结论**：`vibe-skills` 不需要任何自定义 Shell 脚本。遵循 CLAUDE.md 硬规则："能用现成工具就不用自造轮子"。

Skill 的价值在于 **AI 智能层**：知道该执行哪些 `npx skills` 命令、如何解读输出、如何推荐、如何引导用户确认。

## 3. 目标

创建 `vibe-skills` Skill，让 AI 在对话中完成 Skills 完整生命周期管理：

1. **扫描诊断**：调用 `skills ls` / `skills ls -g` 获取现状
2. **问题识别**：AI 分析输出，识别越界、超限、冗余问题
3. **推荐建议**：基于项目特点 + `registry.json` 推荐适合的 skills
4. **确认修复**：分组征询用户，执行对应 `skills add`/`remove` 命令
5. **使用记录**：追踪哪些 skills 被推荐/安装过（写入 `~/.config/vibe/skills-usage.jsonl`）

## 4. 设计方案（精简版）

### 4.1 Skill 目录结构

```
skills/vibe-skills/
├── SKILL.md          # 主文件：AI 对话流程指引 + npx skills 用法指南
└── registry.json     # Skills 推荐注册表（唯一的数据文件）
```

**无 Shell 脚本**：操作全部委托给 `npx skills`。

### 4.2 AI 对话流程

```
触发 vibe-skills
  ↓
AI 执行：npx skills ls && npx skills ls -g
  ↓
AI 分析输出，生成诊断报告（分 3 组）：
  A. 违规项（全局 >10 个 / 项目 >20 个 / 错误层级）
  B. 推荐新增（基于 registry.json + 项目 CLAUDE.md 分析）
  C. 冷门/清理建议
  ↓
逐组征询确认：
  A. "发现 2 个越界 skill，建议移至项目级，确认？[y/n]"
  B. "推荐 5 个 skills，安装哪些？[1/2/3/全部/跳过]"
  C. "有冷门 skill 需要清理吗？[y/n]"
  ↓
用户确认 → AI 执行对应命令：
  npx skills add <pkg> --agent <ide>
  npx skills remove <name> [-g]
```

### 4.3 限额策略（AI 强制执行）

| 层级 | 限额 | 检测命令 |
|------|------|---------|
| 全局 (`~/.xxx/skills/`) | ≤ 10 个（Antigravity 例外） | `skills ls -g` |
| 项目级 (`.xxx/skills/`) | ≤ 20 个 | `skills ls` |

> **Antigravity 例外**：930 个 skills 属于独立管理体系，不计入全局限额。

### 4.4 IDE × Agent 名称映射

| IDE | `--agent` 值 | 全局路径 | 项目路径 |
|-----|-------------|---------|---------|
| Claude Code | `claude-code` | `~/.claude/skills/` | `.claude/skills/` |
| Trae | `trae` | `~/.trae/skills/` | `.trae/skills/` |
| Antigravity | `antigravity` | `~/.gemini/antigravity/skills/` | — |
| Codex | `codex` | `~/.codex/skills/` | — |
| Kiro | `kiro` | `~/.kiro/skills/` | `.kiro/` |
| Superpowers (共享) | `*` | `~/.agents/skills/` | `.agents/skills/` |

### 4.5 registry.json 结构

```json
{
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
    }
  ]
}
```

AI 读取此文件 + 分析项目 `CLAUDE.md` 技术栈 → 过滤出适合当前项目的推荐列表。

### 4.6 推荐的全局核心 skills（≤10 个）

| Skill | 来源 | 用途 |
|-------|------|------|
| `systematic-debugging` | obra/superpowers | 系统性调试 |
| `brainstorming` | obra/superpowers | 需求探索 |
| `verification-before-completion` | obra/superpowers | 防止草率完成 |
| `writing-skills` | obra/superpowers | 创建新 skill |
| `git-pushing` | antigravity | git 提交推送 |

## 5. 边界声明

- **不管理 Antigravity 的 930 个 skills**：独立体系，不干预
- **不跨 worktree 同步**：每个 worktree 独立管理项目级 skills
- **不修改 `.github/copilot-instructions.md`**：Copilot 格式特殊，另行处理
- **不自动执行**：所有操作必须用户确认后才执行

## 6. 执行计划

- [ ] **Step 1 (Spec):** 细化 SKILL.md 对话流程和 CSO 优化（触发条件描述）
- [ ] **Step 2 (Plan):** 拆分实现任务（仅 2 个文件：SKILL.md + registry.json）
- [ ] **Step 3 (Code):** 编写 `registry.json`（录入推荐 skills 数据）
- [ ] **Step 4 (Code):** 编写 `SKILL.md`（含完整对话流程、命令参考）
- [ ] **Step 5 (Code):** 在 `install.sh` 添加 `vibe-skills` 的 symlink 分发
- [ ] **Step 6 (Test):** 模拟对话：触发 → 扫描 → 诊断 → 推荐 → 确认 → 执行
- [ ] **Step 7 (Audit):** 验证 SKILL.md ≤ 500 words，registry.json 完整性
