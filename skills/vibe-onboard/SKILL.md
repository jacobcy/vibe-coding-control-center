---
name: vibe-onboard
description: 安装完成后的入门引导与系统检查。用于安装完成后引导用户完成配置、检查系统状态、介绍核心功能，是新用户安装后的第一步入口。支持交互式询问用户需求，只安装必要的可选组件。**配置驱动**：从 config/dependencies.toml 读取依赖列表。
---

# /vibe-onboard - 安装后入门引导

Vibe Center 安装完成后的一站式引导工具，帮助用户完成全部配置、检查系统状态、了解核心功能，确保系统就绪可用。

**完成后状态**：所有基础配置已完成，系统状态健康，用户了解核心用法，可以开始使用 Vibe Center 开发。

---

## 核心职责

1. **必要依赖诊断检查**：运行 `vibe doctor` 全面检查系统状态，自动修复可解决的问题
2. **密钥配置引导**：引导用户配置必要的 API 密钥（OpenAI/Anthropic/GitHub 等）
3. **交互式可选组件安装**：询问用户需求，按需安装可选组件（远程开发工具、额外AI后端等）
4. **常用功能介绍**：介绍 Vibe Center 的核心功能和常用命令
5. **快速开始教程**：给出简单的使用示例，帮助用户快速上手

**配置驱动设计**：
- 依赖列表来自 `config/dependencies.toml`（单一真源）
- 使用 `uv run python scripts/vibe-read-dependencies.py --format json` 读取配置
- 动态生成检查和引导流程，无需硬编码

---

## 停止点

完成后输出：
- ✅ 系统状态检查完成，所有必要依赖正常
- ✅ 密钥配置已完成
- ✅ 可选组件已按用户需求安装
- **下一步**：开始使用 Vibe Center，运行 `/vibe-new` 创建新任务

---

## 完整流程

```
/vibe-onboard
  ├─ Step 0: 加载配置
  │   ├─ 运行 `uv run python scripts/vibe-read-dependencies.py --format json`
  │   ├─ 解析 JSON 配置，获取所有依赖列表
  │   └─ 根据配置动态生成后续检查和引导流程
  │
  ├─ Step 1: 必要依赖诊断与检查
  │   ├─ 运行 `vibe doctor --essential` 只检查必要依赖
  │   ├─ 自动修复可解决的问题（依赖缺失、权限问题等）
  │   └─ 对于无法自动修复的问题，给出明确的解决方案
  │
  ├─ Step 2: 密钥配置引导
  │   ├─ 从配置读取必要密钥列表（api_keys.essential）
  │   ├─ 检查 `~/.vibe/keys.env` 中的密钥配置
  │   ├─ 列出缺失的必要密钥，引导用户输入配置
  │   └─ 验证密钥有效性
  │
  ├─ Step 3: 交互式可选组件询问（每项都需要用户确认）
  │   ├─ AI开发工具安装？
  │   │   ├─ 运行 `vibe-check-tools.sh` 检查工具状态
  │   │   ├─ 如果未安装任何工具，询问用户选择：
  │   │   │   ├─ Claude Code (付费，功能强大) → 引导安装 claude
  │   │   │   ├─ OpenCode (免费开源) → 执行 `npm install -g opencode`
  │   │   │   └─ 两者都安装 → 按顺序安装
  │   │   └─ 如果已有工具，询问是否安装其他工具
  │   ├─ 从配置读取可选工具列表（tools.optional）
  │   │   ├─ 遍历每个可选工具，询问用户是否需要
  │   │   │   ├─ rtk → Token 优化代理（全局 hook 依赖）
  │   │   │   ├─ gemini → Gemini API CLI
  │   │   │   ├─ tailscale + ncat → 远程开发工具
  │   │   │   ├─ pre-commit → Git hooks 检查
  │   │   │   └─ direnv → 自动环境加载
  │   │   └─ 按用户选择执行安装命令
  │   ├─ 从配置读取可选密钥列表（api_keys.optional）
  │   │   ├─ 遍历每个可选密钥，询问用户是否需要
  │   │   │   ├─ ANTHROPIC_AUTH_TOKEN → Claude Code
  │   │   │   ├─ OPENAI_API_KEY → Codex plugin
  │   │   │   ├─ LINEAR_API_KEY → Linear plugin
  │   │   │   └─ DEEPSEEK_API_KEY → DeepSeek API
  │   │   └─ 引导用户配置到 `~/.vibe/keys.env`
  │
  ├─ Step 4: 核心功能介绍
  │   ├─ 介绍 Vibe Center 的核心定位：AI 开发编排工具
  │   ├─ 展示常用命令：
  │   │   - `/vibe-new`：创建新开发任务
  │   │   - `/vibe-commit`：提交代码并生成规范 commit 信息
  │   │   - `/vibe-review`：代码评审
  │   │   - `vibe doctor`：系统诊断
  │   │   - `vibe keys`：密钥管理
  │   └─ 介绍项目架构和扩展能力
  │
  └─ Step 5: 快速开始教程
      ├─ 给出简单的使用示例：如何创建一个新任务，如何提交代码
      ├─ 说明文档位置：`CLAUDE.md`、`docs/` 目录
      └─ 提示用户有问题可以随时查看 `CLAUDE.md` 或使用 `/help` 获取帮助
```

---

## 配置真源

所有依赖声明位于 [config/dependencies.toml](../../config/dependencies.toml)：

- **必要工具**：git, uv, python, claude-or-opencode, tmux
- **可选工具**：rtk, gemini, tailscale, ncat, pre-commit, direnv
- **必要密钥**：GH_TOKEN, EXA_API_KEY, CONTEXT7_API_KEY
- **可选密钥**：ANTHROPIC_AUTH_TOKEN, OPENAI_API_KEY, LINEAR_API_KEY, DEEPSEEK_API_KEY
- **Claude Plugins**：12 个全局 + 4 个项目级
- **Skills**：4 个核心 + 5 个辅助
- **Workflows**：cockpit 工作流 + 标准开发流程

**读取配置**：
```bash
uv run python scripts/vibe-read-dependencies.py --format json
```

---

## 注意事项

1. **交互式询问**：每一步都需要用户明确确认，不要强制安装不需要的组件
2. **尊重用户选择**：如果用户拒绝某个组件，不要反复提示或强行安装
3. **密钥安全**：密钥输入时要保证安全，不要记录或泄露用户的密钥信息
4. **清晰指引**：对于有问题的检查项，要给出明确、可执行的解决方案
5. **友好引导**：对于不熟悉技术的用户也要容易理解，使用简单明了的语言