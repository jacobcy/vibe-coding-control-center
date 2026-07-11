---
name: vibe-skills-manager
description: Use when installed skills are messy across IDEs, the user is unsure which skills exist globally vs project-level, needs to sync, clean, or recommend installed skills, is setting up a new worktree, or mentions "/vibe-skills-manager". Do not use for authoring or reviewing `skills/vibe-*` content.
---

# Vibe Skills Manager

## Overview

AI 驱动的 skills 体系梳理、差距分析与安装建议工具。

这个 skill 的目标不是自动安装所有东西，而是先把本项目当前的 skills 生态分层说清楚，再根据用户实际启用的 agent 和需求给建议。

## When to Use

用于 skills inventory、安装形态、全局/项目级分布和 symlink 健康检查；不处理一般机器环境或 repo 配置。

## Required Reading

- `docs/standards/v3/skill-standard.md`
- `docs/standards/plugin-setup-standard.md`

## 职责边界

- **负责**：skills 安装形态、全局与项目级分布、symlink 健康、期望配置 vs 实际状态、缺失/冗余分析
- **不负责**：项目导览、机器级安装诊断、repo 配置补全、hooks/MCP/claude-mem 运行态故障

分流规则：

- 机器级安装、CLI、doctor、keys、Claude/Codex 外部工具链问题 → `skills/vibe-onboard/SKILL.md`
- 当前 repo 的工具与环境 readiness → `skills/vibe-project-check/SKILL.md`
- 仅需项目结构/命令索引 → `skills/vibe-instruction/SKILL.md`

如用户讨论的是 Claude / Codex 外部工具链兼容性，而不是 skills inventory，本 skill 只做边界说明，真源应回到：

- `docs/standards/plugin-setup-standard.md`

## 当前 skill 体系

### 1. 支持范围

- 当前稳定目标 agent：Claude Code、Codex、OpenCode、Agy
- 当前维护的第三方能力：claude-mem、superpowers、ponytail、caveman、speckit
- 不再把 Antigravity、Kiro、Gemini、Copilot 等作为默认 skills 安装建议

一句话：
- 确定 GitHub 仓库后，按 agent 选择对应 plugin 安装器
- `npx skills` 只作为明确需要时的 legacy fallback

### 2. OpenSpec

- 属于项目内使用的独立工具链
- 通过 `openspec init --tools claude,codex,opencode` 初始化
- `scripts/init.sh` 负责当前项目 / worktree 的 OpenSpec 初始化
- 有自己独立的命令与 workflow，不并入 `npx skills` 的“第三方通用技能包”语义

### 3. Gstack

- 属于**用户可选安装**的功能增强层
- 提供 QA、部署、浏览器自动化、设计评审等增强技能
- 推荐安装方式：

```bash
git clone --single-branch --depth 1 https://github.com/garrytan/gstack.git ~/.claude/skills/gstack
cd ~/.claude/skills/gstack
./setup
```

- 默认不要求安装，只有用户明确需要这些增强能力时才建议启用

## Execution Flow（工作流程）

```
安装期望 (JSON)  →  声明自动安装集合
可选建议 (YAML)  →  声明非自动增强
实际状态 (JSON)  →  扫描实际安装
Skill 分析      →  对比差距，生成建议
```

## 使用方法

### Step 1: 扫描实际状态

```bash
bash skills/vibe-skills-manager/scan-skills.sh
```

生成实际状态报告：`.agent/reports/skills-state-<timestamp>.json`

### Step 2: 使用 Skill 分析差距

直接对话：`/vibe-skills-manager`

Skill 会：
1. 读取安装期望真源：`config/v3/skills.json`
2. 读取实际状态：`.agent/reports/skills-state-*.json`
3. 对比分析，生成差距报告
4. 按 skill 体系给建议（plugin / `npx skills` / `scripts/init.sh` / 可选增强）
5. 给出建议（需人工确认后执行）

## 期望配置

安装期望真源是 `config/v3/skills.json`；`scripts/install.sh` 将其同步到 `~/.vibe/skills.json`，`scripts/init.sh` 消费 repo-local 或全局副本。`skills-expected.yaml` 仅保留人类可读的可选增强建议，不得覆盖 manifest。

### 配置格式

```yaml
# 全局期望
global:
  claude:
    expected:
      - superpowers-plugin  # Claude 官方 plugin 形态
  codex:
    expected:
      - superpowers-plugin  # Codex plugin 形态
  opencode:
    expected:
      - superpowers-plugin  # OpenCode plugin 形态
  agy:
    expected:
      - ponytail-plugin  # Agy plugin 形态

# 项目级期望
project:
  agents:
    - codex
    - claude-code
    - opencode
    - agy
  packages: []  # 项目自有 vibe-* 由 scripts/init.sh 建立 symlink
```

### 添加期望

需要自动安装的第三方 skill 包写入 `config/v3/skills.json`；仅供推荐、不自动安装的增强能力才写入 `skills-expected.yaml`。

```yaml
global:
  packages:
    - source: namespace/package
      skills:
        - some-cool-tool
```

更新 manifest 后运行 `scripts/init.sh` 安装，并用 `/vibe-skills-manager` 对比实际状态；YAML 中的可选项只在用户需要时建议启用。

## 架构说明

### 目录职责

| 目录 | 用途 | 内容 |
|------|------|------|
| `~/.agents/skills/` | 全局 Superpowers / 其他第三方 skills | 非 plugin Agents 共享 |
| `~/.claude/plugins/` | Claude 官方 plugin 生态 | Claude Code 使用 |
| `~/.claude/skills/` | Claude 本地扩展目录 | 可承载 gstack 等增强层 |
| `.agent/skills/` / `.agents/skills/` | `npx skills` 项目级第三方 | 应避免重复 plugin 已覆盖的 |
| `.codex/skills/` | Codex 项目级入口 | symlink 指向项目自有 vibe-* |
| `skills/` | Native vibe-* | 本项目原生 skills |

### 正确架构

```text
.claude/skills/vibe-check -> ../../skills/vibe-check
.codex/skills/vibe-check  -> ../../skills/vibe-check
```

### 使用策略

- **Claude Code**: 优先使用官方 plugin 形态的 Superpowers；本地增强能力可放在 `~/.claude/skills/`
- **Codex**: 第三方主能力走 `codex plugin`；项目自有 `vibe-*` 由 `.codex/skills/` 暴露
- **其他 Agents**: 非 plugin agent 才使用 `~/.agents/skills/` 下的 Superpowers / 第三方 skills
- **vibe-\***: 本项目原生，通过 symlink 分发
- **OpenSpec**: 自己管理，项目内初始化
- **Gstack**: 用户按需安装，不是默认必需项

## Skill 职责

当用户调用 `/vibe-skills-manager` 时：

1. **读取安装期望**：`config/v3/skills.json`
2. **读取实际状态**：最新的 `.agent/reports/skills-state-*.json`
3. **对比分析**：
   - 冗余检测：重复安装的
   - 缺少检测：期望有但实际没有的
   - Symlink 健康检查
4. **生成建议报告**：保存到 `.agent/reports/skills-analysis-*.md`
5. **按体系给修复建议**：
   - Claude plugin 缺失
   - Codex/Claude plugin 缺失或非 plugin Agent 的 `npx skills` 缺失
   - 项目级 `scripts/init.sh` 同步缺失
   - 用户可选增强（如 gstack）
6. **等待人工确认**：不自动执行，需用户确认后手动处理

## Guardrails

- 只管理 skills 配置、安装建议与同步状态，不接管机器安装或项目配置检查。
- 删除、重装或修改全局配置前必须取得用户确认。
- Claude plugin、第三方 Markdown skills、项目自有 `vibe-*` 必须按各自安装形态判断，不能只比较名称。

## 常见问题

### 如何添加新的期望 skill？

自动安装项编辑 `config/v3/skills.json`；仅推荐项编辑 `skills-expected.yaml`。下次扫描与分析时检查 manifest 和实际状态的差距。

### 如何修复冗余？

根据 Skill 分析报告中的建议，人工确认后手动删除：

```bash
rm -rf .agents/skills/<冗余skill>
```

### 如何修复项目级 symlink 问题？

```bash
scripts/init.sh
```

### 如何安装 Gstack？

按需安装，不作为默认必需项：

```bash
git clone --single-branch --depth 1 https://github.com/garrytan/gstack.git ~/.claude/skills/gstack
cd ~/.claude/skills/gstack
./setup
```

## 文件说明

- `config/v3/skills.json` - 自动安装期望真源
- **[skills-expected.yaml](skills-expected.yaml)** - 可选增强建议
- **[scan-skills.sh](scan-skills.sh)** - 实际状态扫描脚本
- **SKILL.md** - 本文档
- `.agent/reports/skills-state-*.json` - 实际状态报告（自动生成）
- `.agent/reports/skills-analysis-*.md` - 差距分析报告（Skill 生成）
