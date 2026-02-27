# Vibe Center 2.0

Vibe Center 是面向 AI 协作开发的轻量编排工具：统一工具安装、密钥管理、工作流流转与规则治理。

## 能力
- 工具管理：`vibe tool`
- 环境诊断：`vibe check`
- 密钥管理：`vibe keys`
- 研发流程：`vibe flow`
- Agent 规则与上下文：`.agent/`

## 快速开始
```bash
export PATH="/path/to/vibe-center/main/bin:$PATH"
source config/aliases.sh

vibe check
vibe keys init
vibe tool
```

## 命令
```bash
vibe check
vibe tool
vibe keys <list|set|get|init>
vibe flow <start|review|pr|done|status|sync>
```

## 结构
- `bin/` CLI 入口
- `lib/` 核心模块
- `config/` 配置与 aliases
- `skills/` Agent 技能
- `.agent/` 规则、上下文、工作流

## 文档

> **单一事实原则**：每个文档有明确的职责边界，详见 [SOUL.md](SOUL.md) §0

- **[SOUL.md](SOUL.md)**：项目宪法和核心原则（权威）
- **[STRUCTURE.md](STRUCTURE.md)**：项目结构定义（权威）
- **[CLAUDE.md](CLAUDE.md)**：项目上下文与硬规则（AI 必读）
- **[AGENTS.md](AGENTS.md)**：AI Agent 入口指南
- **[DEVELOPER.md](DEVELOPER.md)**：开发者指南（开发流程权威）
- **[docs/](docs/)**：人类文档区（详见 [docs/README.md](docs/README.md)）
