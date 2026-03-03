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
# 1. 全局安装 (将核心分发至 ~/.vibe)
zsh scripts/install.sh

# 2. 重载 Shell (或重启终端)
source ~/.zshrc

# 3. 基础依赖与环境诊断
vibe tool deps
vibe doctor
```

## 命令
```bash
vibe check
vibe tool
vibe keys <list|set|get|init>
vibe flow <start|review|pr|done|status|sync>
```

## 架构分层 (三层解耦)
Vibe Center 3.0 推行了极其稳定的抽象分层模型：

1. **Tier 3 (认知层 & 流程编排): Supervisor (Vibe Gate)**
   - 开发流程式的宪法，如 OpenSpec 与 Vibe Gate，决定需求的进入和交付规范。
2. **Tier 2 (胶水层 & 智能辅助): Vibe Skills (Slash Commands)**
   - `skills/` 下的指令代理 (`/vibe-task`, `/vibe-save` 等)，纯靠只读与派发请求工作。它们包装了底层的复杂性，专门向 AI 提供上下文拼装能力。
3. **Tier 1 (物理真源层 & 绝对执行): Shell Commands & Aliases**
   - Vibe Shell 组 (`vibe flow`, `vibe task`) 和基于 Zsh 的 Alias 工具组 (`wtnew`)。只在这里进行数据源（`registry.json`）与分支的物理读写。

## 结构目录语义
- `bin/` & `lib/` (Tier 1): CLI 和核心执行器（物理源）
- `config/` (Tier 1): Alias 定义及配置文件
- `skills/` (Tier 2): Vibe Agent Slash 技能库所在处
- `.agent/`: (Tier 3): 流程、规则和智能上下文（含跨团队共识 `memory.md` 与本地未追踪的忽略缓冲区 `task.md`）

## 文档

> **单一事实原则**：每个文档有明确的职责边界，详见 [SOUL.md](SOUL.md) §0

- **[SOUL.md](SOUL.md)**：项目宪法和核心原则（权威）
- **[STRUCTURE.md](STRUCTURE.md)**：项目结构定义（权威）
- **[CLAUDE.md](CLAUDE.md)**：项目上下文与硬规则（AI 必读）
- **[AGENTS.md](AGENTS.md)**：AI Agent 入口指南
- **[DEVELOPER.md](DEVELOPER.md)**：开发者指南（开发流程权威）
- **[docs/](docs/)**：人类文档区（详见 [docs/README.md](docs/README.md)）
