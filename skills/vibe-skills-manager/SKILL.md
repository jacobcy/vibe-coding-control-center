---
name: vibe-skills-manager
description: Use when installed skills are messy across IDEs, the user is unsure which skills exist globally vs project-level, needs to sync, clean, or recommend installed skills, is setting up a new worktree, or mentions "/vibe-skills-manager". Do not use for authoring or reviewing `skills/vibe-*` content.
user-invocable: true
---

# Vibe Skills Manager

AI 驱动的 skills 体系梳理、差距分析与安装建议工具。

这个 skill 的目标不是自动安装所有东西，而是先把本项目当前的 skills 生态分层说清楚，再根据用户实际启用的 agent 和需求给建议。

## 当前 skill 体系

### 1. Superpowers

- **Claude Code**：优先走官方 plugin 生态
- **其他 Agents**：优先走 `npx skills add obra/superpowers ...`
- **本项目角色**：`scripts/init.sh` 负责把项目内可见层和本地 symlink 层准备好，但不替代全局安装

一句话：
- Claude 用 plugin
- 其他 agent 用 `npx skills`

### 2. OpenSpec

- 属于项目内使用的独立工具链
- 通过 `openspec init --tools ...` 初始化
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

## 工作流程

```
期望配置 (YAML)  →  声明人类期望
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
1. 读取期望配置：[skills-expected.yaml](skills-expected.yaml)
2. 读取实际状态：`.agent/reports/skills-state-*.json`
3. 对比分析，生成差距报告
4. 按 skill 体系给建议（plugin / `npx skills` / `scripts/init.sh` / 可选增强）
5. 给出建议（需人工确认后执行）

## 期望配置

文件：[skills-expected.yaml](skills-expected.yaml)

### 配置格式

```yaml
# 全局期望
global:
  claude:
    expected:
      - superpowers-plugin  # Claude 官方 plugin 形态
  agents:
    expected:
      - superpowers  # 其他 Agents 的 npx skills 形态

# 项目级期望
project:
  managed:
    - openspec   # OpenSpec 独立工具链
    - vibe-star  # 本项目原生 vibe-*
  optional:
    - gstack     # 用户可选增强
```

### 添加期望

如果项目以后要增加新的“可选增强技能包”，优先写到 `optional`，不要直接写进必需集合。

```yaml
project:
  optional:
    some-cool-tool:
      description: 项目可选增强能力
      install: npx skills add namespace/skill-name
```

然后由 `/vibe-skills-manager` 在用户需要时再建议启用。

## 架构说明

### 目录职责

| 目录 | 用途 | 内容 |
|------|------|------|
| `~/.agents/skills/` | 全局 Superpowers / 其他第三方 skills | 非 Claude Agents 共享 |
| `~/.claude/plugins/` | Claude 官方 plugin 生态 | Claude Code 使用 |
| `~/.claude/skills/` | Claude 本地扩展目录 | 可承载 gstack 等增强层 |
| `.agents/skills/` | 项目级第三方 | 应避免重复全局已有的 |
| `.agent/skills/` | 项目级 Agents 可见 | ✅ symlink 指向全局或 vibe-* |
| `skills/` | Native vibe-* | 本项目原生 skills |

### 正确架构

```
.agent/skills/
├── brainstorming -> ~/.agents/skills/brainstorming  # ✅ symlink
├── vibe-check -> ../../skills/vibe-check           # ✅ symlink
└── openspec-*                                       # OpenSpec 管理

.claude/skills/
└── vibe-check -> ../../skills/vibe-check           # ✅ symlink
```

### 使用策略

- **Claude Code**: 优先使用官方 plugin 形态的 Superpowers；本地增强能力可放在 `~/.claude/skills/`
- **其他 Agents**: 主要使用 `~/.agents/skills/` 下的 Superpowers / 第三方 skills
- **vibe-\***: 本项目原生，通过 symlink 分发
- **OpenSpec**: 自己管理，项目内初始化
- **Gstack**: 用户按需安装，不是默认必需项

## Skill 职责

当用户调用 `/vibe-skills-manager` 时：

1. **读取期望配置**：`skills-expected.yaml`
2. **读取实际状态**：最新的 `.agent/reports/skills-state-*.json`
3. **对比分析**：
   - 冗余检测：重复安装的
   - 缺少检测：期望有但实际没有的
   - Symlink 健康检查
4. **生成建议报告**：保存到 `.agent/reports/skills-analysis-*.md`
5. **按体系给修复建议**：
   - Claude plugin 缺失
   - 其他 Agent 的 `npx skills` 缺失
   - 项目级 `scripts/init.sh` 同步缺失
   - 用户可选增强（如 gstack）
6. **等待人工确认**：不自动执行，需用户确认后手动处理

## 常见问题

### 如何添加新的期望 skill？

编辑 `skills-expected.yaml`，添加到对应位置。下次运行 Skill 分析时会检测到缺失。

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

- **[skills-expected.yaml](skills-expected.yaml)** - 期望配置（YAML，易读易编辑）
- **[scan-skills.sh](scan-skills.sh)** - 实际状态扫描脚本
- **SKILL.md** - 本文档
- `.agent/reports/skills-state-*.json` - 实际状态报告（自动生成）
- `.agent/reports/skills-analysis-*.md` - 差距分析报告（Skill 生成）
