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
    timestamp: "2026-02-28T21:49:00+08:00"
    reason: 需求通过 brainstorming 完整探讨，用户已确认方向
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

当前系统中 Skills 混乱。项目有 7 种 AI 工具（Claude Code、Trae、Antigravity、Kiro、Codex、Copilot、OpenCode），每种工具有独立的 skills 目录（全局 `~/.xxx/skills/` 和项目级 `.xxx/skills/`），导致：

- **层级混乱**：项目级 skills 泄漏到全局（如 `~/.agents/skills/` 里出现 `vibe-boundary-check`）
- **数量失控**：全局 930+ skills（Antigravity）、项目级无上限
- **跨工具冗余**：同一 skill 在 7 个 IDE 目录重复存储，靠 symlink 维持一致性但缺乏统一管理
- **冷热不知**：不知道哪些 skills 常用、哪些从未被调用
- **推荐盲目**：新项目不知道该装哪些 skills

## 2. 目标

创建 `vibe-skills` Skill，实现 AI 对话驱动的 Skills 生命周期管理：

1. **扫描诊断**：检测所有 IDE skills 目录的现状（通过轻量 Shell 脚本）
2. **问题识别**：AI 分析报告，识别越界、冗余、违规项
3. **推荐建议**：基于项目特点推荐适合的 skills 和 MCP 插件
4. **确认修复**：分组征询用户确认，调用 Shell 脚本执行操作
5. **使用追踪**：记录 skill 调用频率，累积热度数据

## 3. 设计方案

### 3.1 核心原则

- **Shell 脚本只做原子操作**：scan（输出 JSON）、install（`npx skills`）、remove（删除/解链）
- **逻辑全在 Agent**：分析、推荐、决策、交互，全部在对话中完成
- **用户偏好持久化**：`~/.config/vibe/skills-preferences.json`，跨 worktree 共享

### 3.2 Skill 目录结构

```
skills/vibe-skills/
├── SKILL.md              # 主文件：AI 对话流程指引
├── scan.sh               # 扫描脚本：输出 skills-report.json
├── install.sh            # 安装脚本：npx skills add <name> --agent <ide>
├── remove.sh             # 删除脚本：rm symlink 或 rm -rf real dir
└── registry.json         # Skills 注册表：已知 skills 的元数据
```

数据存放（全局持久）：
```
~/.config/vibe/
├── skills-preferences.json   # 用户偏好（IDE 列表、限额）
└── skills-usage.jsonl        # 使用追踪（append-only）
```

安装后通过 `install.sh` 软链到各 IDE 目录：
```
skills/vibe-skills/ → .agent/skills/vibe-skills
skills/vibe-skills/ → .trae/skills/vibe-skills
```

### 3.3 Shell 脚本职责（轻量）

**`scan.sh`** — 只收集数据，不判断：
```
输入：无
处理：遍历 7 个 IDE 的 global/project skills 目录
      读取 ~/.config/vibe/skills-preferences.json
      读取 ~/.config/vibe/skills-usage.jsonl（统计调用频率）
输出：~/.config/vibe/skills-report.json
内容：{
  "scanned_at": "ISO8601",
  "global_skills": { "claude": [...], "trae": [...], ... },
  "project_skills": { "claude": [...], "trae": [...], ... },
  "usage_stats": { "skill-name": { "count": N, "last_used": "ISO8601" } }
}
```

**`install.sh`** — 单纯安装：
```
参数：<skill-name> [--agent <ide>] [--global]
执行：npx skills add <skill-name> --agent <ide>
      或 ln -sf <source> <target>
```

**`remove.sh`** — 单纯删除：
```
参数：<path>
执行：[[ -L "$1" ]] && unlink "$1" || rm -rf "$1"
```

### 3.4 AI 对话流程

```
触发 vibe-skills
  ↓
调用 scan.sh → 读 skills-report.json
  ↓
呈现诊断报告（分 3 组）：
  A. 违规项（越界/超限）
  B. 推荐新增（基于项目特点分析）
  C. 冷门清理建议（>30天未用）
  ↓
逐组征询确认：
  "发现 2 个问题，建议修复？[y/n/详细]"
  "推荐 5 个 skills，选择安装哪些？[编号]"
  "8 个冷门，清理哪些？[编号/全部/跳过]"
  ↓
用户确认 → 调用 install.sh / remove.sh
  ↓
追加记录到 skills-usage.jsonl
```

### 3.5 限额策略

| 层级 | 限额 | 说明 |
|------|------|------|
| 全局 (`~/.xxx/skills/`) | ≤ 10 个 | 跨项目通用核心 skills |
| 项目级 (`.xxx/skills/`) | ≤ 20 个 | 项目特定 skills（含 symlinks） |

### 3.6 IDE Skills 目录映射

| IDE | 全局路径 | 项目路径 | 安装命令 |
|-----|---------|---------|---------|
| Claude Code | `~/.claude/skills/` | `.agent/skills/` | `npx skills add --agent claude` |
| Trae | `~/.trae/skills/` | `.trae/skills/` | `npx skills add --agent trae` |
| Antigravity | `~/.gemini/antigravity/skills/` | — | `npx skills add --agent antigravity` |
| Codex | `~/.codex/skills/` | — | 手动 |
| Kiro | `~/.kiro/skills/` | `.kiro/` | 手动 |
| Copilot | — | `.github/` | instructions 文件 |
| Superpowers (共享) | `~/.agents/skills/` | `.agents/skills/` | `npx skills add obra/superpowers` |

### 3.7 registry.json 结构

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
      "recommended": true
    }
  ]
}
```

### 3.8 推荐逻辑（Agent 执行）

1. 读取 `CLAUDE.md` + `SOUL.md` 提取技术栈关键词
2. 对比 `registry.json` 按 `project_types` 过滤
3. 排除已安装的
4. 结合 `usage_stats` 按调用热度加权排序
5. 输出 Top 10 推荐

## 4. 边界 & 排除

- **不管理 Antigravity 的 930 个 skills**：体量太大，auto-managed by Antigravity 自身
- **不修改 `.github/copilot-instructions.md`**：格式不同，另行处理
- **不跨 worktree 同步**：每个 worktree 独立管理项目级 skills

## 5. 执行计划

- [ ] **Step 1 (Spec):** 细化 SKILL.md 的对话流程、触发条件、CSO 优化
- [ ] **Step 2 (Plan):** 拆分实现任务（4 个文件：SKILL.md + 3 个 sh + registry.json）
- [ ] **Step 3 (Code):** 编写 scan.sh / install.sh / remove.sh
- [ ] **Step 4 (Code):** 编写 SKILL.md 主文件（含对话流程指引）
- [ ] **Step 5 (Code):** 初始化 registry.json（录入当前已知 skills）
- [ ] **Step 6 (Code):** 添加到 install.sh 的 symlink 分发逻辑
- [ ] **Step 7 (Test):** 运行 scan.sh 验证 JSON 输出
- [ ] **Step 8 (Test):** 模拟对话流程验证 AI 逻辑
- [ ] **Step 9 (Audit):** 检查 LOC（3 个 sh 脚本总行数应 < 150 行）
