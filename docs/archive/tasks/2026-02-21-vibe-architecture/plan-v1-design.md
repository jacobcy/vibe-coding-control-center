# Vibe Coding 环境架构重构设计方案

## 概述

本文档描述 Vibe Coding Control Center 的架构重构方案，目标是提供更工程化、更易用的环境管理体验。

## 背景

当前项目存在以下问题：
1. **配置分散** - 不同 AI 工具的配置散落在各自目录
2. **缺乏工程化结构** - 配置组织不够规范
3. **环境复制困难** - 新机器搭建步骤繁琐
4. **交互方式单一** - 纯命令式，不够自然

## 设计目标

| 目标 | 描述 |
|------|------|
| 工程化结构 | 清晰的目录组织，配置集中管理 |
| 环境可复制 | 一键导出/导入配置 |
| 双轨交互 | 结构化命令 + 自然语言 |
| 扩展性 | 易于添加新工具和新功能 |

## 架构设计

### 目录结构

```
~/.vibe/
├── vibe.yaml              # 主配置文件（单一入口点）
├── keys/                  # 密钥管理
│   ├── anthropic.env      # Anthropic 密钥组
│   ├── openai.env         # OpenAI 密钥组
│   ├── deepseek.env       # DeepSeek 密钥组
│   └── current -> anthropic.env  # 当前激活（符号链接）
│
├── tools/                 # 工具模块
│   ├── claude/
│   │   ├── config.yaml    # 工具配置
│   │   └── mcp.yaml      # MCP 服务器配置
│   └── opencode/
│       ├── config.yaml
│       └── mcp.yaml
│
├── mcp/                   # 共享 MCP 服务器
│   └── servers.yaml
│
└── skills/               # 共享 Skills
    └── *.skill.yaml
```

### vibe.yaml 主配置

```yaml
version: "1.0"
name: "my-vibe-env"

# 密钥管理
keys:
  current: anthropic

# 工具配置
tools:
  claude:
    enabled: true
    default: true
  opencode:
    enabled: true

# MCP 服务器
mcp:
  - github
  - brave-search

# 默认设置
defaults:
  editor: cursor
  shell: zsh
```

### 密钥组配置

```bash
# ~/.vibe/keys/anthropic.env
ANTHROPIC_AUTH_TOKEN=sk-ant-...
ANTHROPIC_BASE_URL=https://api.anthropic.com
ANTHROPIC_MODEL=claude-sonnet-4-5

# ~/.vibe/keys/openai.env
OPENAI_API_KEY=sk-...
OPENAI_BASE_URL=https://api.openai.com
```

## 命令设计

### 密钥管理

```bash
vibe keys list              # 列出所有密钥组
vibe keys use <provider>    # 切换密钥组（如 anthropic, openai）
vibe keys current           # 显示当前密钥组
vibe keys set KEY=value    # 设置当前组的密钥
```

### 工具管理

```bash
vibe tool list              # 列出可用工具
vibe tool install <name>    # 安装工具
vibe tool uninstall <name>  # 卸载工具
vibe tool default <name>    # 设置默认工具
```

### MCP 管理

```bash
vibe mcp list               # 列出 MCP 服务器
vibe mcp add <name>        # 添加 MCP
vibe mcp remove <name>     # 移除 MCP
vibe mcp enable <name> --for <tool>  # 为特定工具启用
```

### Skill 管理

```bash
vibe skill list             # 列出 skills
vibe skill add <path>      # 添加 skill
vibe skill remove <name>    # 移除 skill
```

### 环境管理

```bash
vibe init                   # 初始化环境
vibe export                 # 导出配置（用于复制）
vibe doctor                 # 诊断问题
```

### 魔法入口

```bash
# 通过 vibe chat 支持自然语言
vibe chat "切换到 deepseek"
vibe chat "安装 opencode"
vibe chat "加个 github mcp"
```

## vibe chat 设计

### 功能定位

vibe chat 是智能对话入口，支持两种模式：

1. **配置/工具操作** - 理解自然语言，执行 vibe 命令
2. **简单问答** - 直接调用 AI 工具回答

### 意图识别

| 输入示例 | 识别意图 | 执行命令 |
|---------|---------|---------|
| "切换到 anthropic" | keys_use | vibe keys use anthropic |
| "安装 opencode" | tool_install | vibe tool install opencode |
| "加个 github mcp" | mcp_add | vibe mcp add github |
| "今天星期几" | simple_chat | claude "今天星期几" |

### 实现方式

1. 预定义意图映射表（关键词匹配）
2. 匹配到已知意图 → 转换为结构化命令执行
3. 未匹配 → 调用 Claude/OpenCode 处理

## 实施计划

### Phase 1: 核心架构

1. 重构目录结构
2. 实现 vibe.yaml 配置系统
3. 迁移现有配置

### Phase 2: 命令实现

1. vibe keys 子命令
2. vibe tool 子命令
3. vibe mcp/skill 子命令
4. vibe init/export 功能

### Phase 3: 智能交互

1. vibe chat 意图识别
2. 自然语言到命令转换
3. 项目上下文 Agent

## 兼容性

- 保持现有别名兼容（c, o, vibe flow 等）
- 新架构与旧配置可共存
- 渐进式迁移

## 附录

### 术语表

| 术语 | 定义 |
|------|------|
| 密钥组 | 一组相关的 API 密钥（如 anthropic.env） |
| 工具模块 | 特定 AI 工具的配置和依赖 |
| 魔法入口 | 支持自然语言的 vibe chat |

### 相关文件

- SOUL.md - 核心原则
- CLAUDE.md - 项目配置
