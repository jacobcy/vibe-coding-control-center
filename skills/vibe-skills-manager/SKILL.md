---
name: vibe-skills-manager
description: Use when installed skills are messy across IDEs, the user is unsure which skills exist globally vs project-level, needs to sync, clean, or recommend installed skills, is setting up a new worktree, or mentions "/vibe-skills-manager". Do not use for authoring or reviewing `skills/vibe-*` content.
user-invocable: true
---

# Vibe Skills Manager

AI 驱动的 Skills 差距分析与健康检查。

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
4. 给出建议（需人工确认后执行）

## 期望配置

文件：[skills-expected.yaml](skills-expected.yaml)

### 配置格式

```yaml
# 全局期望
global:
  claude:
    expected:
      - ECC  # Everything Claude Code
  agents:
    expected:
      - superpowers  # 开发方法论工具集

# 项目级期望
project:
  managed:
    - openspec   # OpenSpec 自动管理
    - vibe-star  # 本项目原生 vibe-*
  additional: []  # 项目特定 skills
```

### 添加期望

如果想安装额外的全局 skill：

```yaml
global:
  agents:
    expected:
      - superpowers
      - some-cool-tool  # 新增
```

Skill 会检测到 `some-cool-tool` 缺失并给出建议。

## 架构说明

### 目录职责

| 目录 | 用途 | 内容 |
|------|------|------|
| `~/.agents/skills/` | 全局 Superpowers | 所有 Agents 共享 |
| `~/.claude/skills/` | 全局 ECC | 仅 Claude Code 使用 |
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

**避免**：
```
.agents/skills/
└── brainstorming/  # ✗ 冗余！全局已有
```

### 使用策略

- **Claude Code**: 主要使用 ECC (`~/.claude/skills/`)
- **其他 Agents**: 主要使用 Superpowers (`~/.agents/skills/`)
- **vibe-\***: 本项目原生，通过 symlink 分发
- **OpenSpec**: 自己管理

## Skill 职责

当用户调用 `/vibe-skills-manager` 时：

1. **读取期望配置**：`skills-expected.yaml`
2. **读取实际状态**：最新的 `.agent/reports/skills-state-*.json`
3. **对比分析**：
   - 冗余检测：重复安装的
   - 缺少检测：期望有但实际没有的
   - Symlink 健康检查
4. **生成建议报告**：保存到 `.agent/reports/skills-analysis-*.md`
5. **等待人工确认**：不自动执行，需用户确认后手动处理

## 常见问题

### 如何添加新的期望 skill？

编辑 `skills-expected.yaml`，添加到对应位置。下次运行 Skill 分析时会检测到缺失。

### 如何修复冗余？

根据 Skill 分析报告中的建议，人工确认后手动删除：

```bash
rm -rf .agents/skills/<冗余skill>
```

### 如何修复 symlink 问题？

```bash
scripts/init.sh
```

## 文件说明

- **[skills-expected.yaml](skills-expected.yaml)** - 期望配置（YAML，易读易编辑）
- **[scan-skills.sh](scan-skills.sh)** - 实际状态扫描脚本
- **SKILL.md** - 本文档
- `.agent/reports/skills-state-*.json` - 实际状态报告（自动生成）
- `.agent/reports/skills-analysis-*.md` - 差距分析报告（Skill 生成）