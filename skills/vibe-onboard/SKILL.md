---
name: vibe-onboard
description: 安装完成后的入门引导与系统检查。用于安装完成后引导用户完成配置、检查系统状态、介绍核心功能，是新用户安装后的第一步入口。支持交互式询问用户需求，只安装必要的可选组件。
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
  ├─ Step 1: 必要依赖诊断与检查
  │   ├─ 运行 `vibe doctor --essential` 只检查必要依赖
  │   ├─ 自动修复可解决的问题（依赖缺失、权限问题等）
  │   └─ 对于无法自动修复的问题，给出明确的解决方案
  │
  ├─ Step 2: 密钥配置引导
  │   ├─ 检查 `~/.vibe/keys.env` 中的密钥配置
  │   ├─ 列出缺失的必要密钥，引导用户输入配置
  │   └─ 验证密钥有效性
  │
  ├─ Step 3: 交互式可选组件询问（每项都需要用户确认）
  │   ├─ 远程开发需求？
  │   │   ├─ Yes → 询问是否使用Tailscale？
  │   │   │   ├─ Yes → 安装 tailscale、ncat，配置 SSH ProxyCommand，添加 tsu alias
  │   │   │   └─ No → 跳过Tailscale相关组件
  │   │   └─ No → 跳过整个远程开发组件
  │   ├─ 使用Gemini作为额外AI后端？
  │   │   ├─ Yes → 检查gemini CLI，未安装则引导安装
  │   │   └─ No → 跳过gemini相关检查
  │   ├─ 使用MCP扩展？
  │   │   ├─ Yes → 安装 mcp 可选依赖 (`uv sync --extra mcp`)
  │   │   └─ No → 跳过mcp安装
  │   ├─ 使用pre-commit hooks？
  │   │   ├─ Yes → 安装 pre-commit，配置 hooks
  │   │   └─ No → 跳过pre-commit安装
  │   └─ 使用direnv自动环境加载？
  │       ├─ Yes → 安装 direnv，配置 shell hook 和 .envrc
  │       └─ No → 跳过direnv安装
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
      └─ 提示用户有问题可以随时使用 `/vibe-help` 寻求帮助
```

---

## 依赖分类

### 必要依赖（强制检查和安装）
- **git**：版本控制核心
- **uv**：Python包管理器
- **claude** 或 **opencode**：至少需要一个AI开发工具
- **Python 3.12+**：运行Vibe 3.0
- **核心Python包**：typer、rich、pydantic、litellm等（install.sh已安装）

### 可选依赖（按用户需求安装）
- **远程开发工具**：
  - tailscale：Tailscale VPN连接
  - ncat/nmap：SSH ProxyCommand支持
  - tsu.sh：Tailscale管理脚本
  - SSH Agent：密钥管理
- **AI后端扩展**：
  - gemini CLI：Gemini API支持
  - mcp：MCP协议扩展
- **开发辅助工具**：
  - pre-commit：代码提交检查
  - direnv：自动环境加载
  - supervisor：后台服务管理

---

## 注意事项

1. **交互式询问**：每一步都需要用户明确确认，不要强制安装不需要的组件
2. **尊重用户选择**：如果用户拒绝某个组件，不要反复提示或强行安装
3. **密钥安全**：密钥输入时要保证安全，不要记录或泄露用户的密钥信息
4. **清晰指引**：对于有问题的检查项，要给出明确、可执行的解决方案
5. **友好引导**：对于不熟悉技术的用户也要容易理解，使用简单明了的语言