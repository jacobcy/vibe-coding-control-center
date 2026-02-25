# Vibe Center 2.0

Vibe Center 2.0 是一个 **极简的 AI 开发编排工具 (Minimalist orchestration tool)**。
它基于 "Cognition First" 原则构建（详见 [SOUL.md](SOUL.md)），旨在简化工具链管理、工作区调度、环境变量同步和常规代码工作流编排。

## 🎯 核心定位

**我们做的事情：**
- **⚙️ AI 工具管理**: 一键安装和配置 Claude、OpenCode、Codex 等工具 (`bin/vibe tool`)
- **🔑 密钥管理**: 集中化、安全的 API 环境密钥管理 (`bin/vibe keys`)
- **🚀 流程编排**: 生命周期管理 (`start` → `review` → `pr` → `done`)
- **💻 终端快捷增强**: 基于 `aliases.sh` 提供高频 Shell Aliases

**我们不做的事情：**
- 本项目**不是** AI Agent 的直接底层实现，而是调度者。
- 不做 NLP 意图路由。
- 不做自定义测试框架或过度工程化的状态机。

## 📂 核心目录结构

遵循极致轻量的 "Zero Dead Code" 设计理念：

```text
vibe-center/
├── bin/vibe             # CLI 分发主入口 (~60 lines)
├── lib/                 # 核心模块业务逻辑库 (限制每个文件 < 200 lines)
│   ├── utils.sh         # 工具与日志函数
│   ├── config.sh        # 配置与路径检测
│   ├── check.sh         # 系统依赖诊断模块
│   ├── tool.sh         # 工具按需安装模块
│   ├── keys.sh          # 密钥生命周期模块
│   └── flow.sh          # 开发工作流编排模块
├── config/              # 配置与 alias 集合 (keys.env 将在此初始化)
├── tests/               # bats-core 基础自测用例
└── .agent/              # Agent 认知工作区 (context, plans, skills, workflows)
```

## 🚀 快速开始

### 1. 基础配置
首先配置 PATH 与 Alias 以获取完整的体验。你也可以将这些写入到 `~/.zshrc` 中：

```bash
# 将 bin 目录添加到 PATH 中 (或直接使用相对/绝对路径)
export PATH="/path/to/vibe-center/main/bin:$PATH"

# 加载 alias 快捷别名
source config/aliases.sh
```

### 2. 环境诊断
检查必须系统依赖和路径配置状态：
```bash
vibe check
```

### 3. 配置 API 密钥
生成并写入所需要的 API 环境参数：
```bash
vibe keys init      # 基于 template 复制初始 keys.env
vibe keys set ANTHROPIC_AUTH_TOKEN "your_token"
vibe keys list      # 查看配置写入状态
```

### 4. 依赖安装
一键对齐所需要的 AI 工具并自动验证：
```bash
vibe tool
```

## 🔄 生命周期工作流 (vibe flow)

使用 `vibe flow` 原接管特性开发全生命周期：

- `vibe flow start <feature-name>`: 创建新分支、初始化工作任务与知识上下文。
- `vibe flow status`: 查看当前系统上下文与开发状态。
- `vibe flow review`: 运行本地检查、lint 与代码审查流。
- `vibe flow pr`: 自动打包提交变更并建立 Pull Request。
- `vibe flow done`: 闭环结束任务，自动清理工作区流并归档总结。

## 📚 开发者与 Agent 指南

本项目处于强有力的规模控制下，所有 `lib/` 和 `bin/` 代码行数总和红线被锁定在 **1,200 行以内**。

了解更多架构约定、行为边界规范，请**在贡献前务必阅读**以下文件：
- **[CLAUDE.md](CLAUDE.md)** - 开发技术栈、代码要求与硬性治理拦截规则。
- **[SOUL.md](SOUL.md)** - 本计划核心心智与不可动摇的基本原则。
- **[AGENTS.md](AGENTS.md)** - 指导全线 AI Agent 的工作接入口及工作标准说明。
- **[.agent/README.md](.agent/README.md)** - Agent 私有工作区规范。
