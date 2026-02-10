# Vibe Coding Control Center

一个专注于开发者生产力的 AI 开发工具管理套件。目标是打造方便快捷的 Vibe Coding 开发环境，提供统一入口来初始化项目、管理 AI 工具（Claude / OpenCode / Codex）并配置开发环境。

**特别说明（目标态）**：
- **Claude**: 通过环境变量切换端点与模型；中国环境默认中转站 `https://api.bghunt.cn`
- **OpenCode**: 原生支持多模型（Qwen、DeepSeek、Moonshot）
- **Codex**: 作为第三优先级工具补位使用

**当前阶段**：功能持续迭代中，以可用性与稳定性优先。

## 核心特性（目标态）

- **菜单驱动界面**: 易用的控制中心，直观的导航
- **项目快速初始化**: 使用最佳实践快速设置新项目
- **智能版本管理**: 自动检测版本、支持一键更新 ⭐ 新功能
- **配置智能合并**: MCP 配置合并而非覆盖，保留自定义设置 ⭐ 新功能
- **安全优先**: 全面的输入验证和安全文件操作
- **模块化设计**: 组织良好的脚本和共享工具库
- **MCP 集成**: 支持 Model Context Protocol（网页搜索、GitHub 访问等）
- **多工具支持**: Claude / OpenCode / Codex（按优先级组织）
- **环境变量一键切换**: 基于 `config/keys.env` + alias 快速切换
- **Worktree 隔离**: 每个 agent 独立目录与 Git 身份
- **国际化支持**: 内建多语言支持
- **现代化架构**: 插件系统、缓存机制、高级错误处理

## 系统要求

- Unix/Linux/macOS 环境
- Git
- Zsh
- Node.js（用于 MCP 服务器）
- jq（推荐，用于 JSON 操作）

## 快速开始

### 1. 现代化安装

使用新的简化安装脚本：

```bash
./scripts/install.sh
```

或者传统的安装方式：

```bash
./install/install-claude.sh
```

这将会：
- 安装 Claude CLI
- 创建配置目录
- 配置 MCP 服务器（GitHub、Brave Search 等）
- 创建命令别名

### 2. 安装 OpenCode（可选）

```bash
./install/install-opencode.sh
```

OpenCode 原生支持多种中国模型，无需额外配置。

## 配置

### API 密钥配置（可选）

你可以用多种方式配置密钥：`config/keys.env`、系统环境变量，或工具自带的登录流程（如 `auth login`）。  
若使用 `config/keys.env`，按以下方式填写：

   **重要**：统一使用 `ANTHROPIC_AUTH_TOKEN`，不要使用 `ANTHROPIC_API_KEY`

   ```bash
   # Claude Code（官方 Anthropic API）
   ANTHROPIC_AUTH_TOKEN=sk-ant-xxxxx
   ANTHROPIC_BASE_URL=https://api.anthropic.com
   ANTHROPIC_MODEL=claude-3-5-sonnet-20241022

   # 中国默认：使用中转站（无需本机代理）
   ANTHROPIC_AUTH_TOKEN=sk-ant-xxxxx
   ANTHROPIC_BASE_URL=https://api.bghunt.cn
   ANTHROPIC_MODEL=claude-3-5-sonnet-20241022

   # GitHub（用于 MCP）
   GITHUB_PERSONAL_ACCESS_TOKEN=github_pat_xxxxx

   # 其他可选的 API 密钥
   BRAVE_API_KEY=BSAwxxxxx
   DEEPSEEK_API_KEY=sk-xxxxx  # OpenCode 可选
   MOONSHOT_API_KEY=sk-xxxxx  # OpenCode 可选
   ```

3. 重新加载配置（如果你使用了 `config/keys.env` 或别名）：
   ```bash
   source ~/.zshrc
   ```

## 使用方法

### 主控制中心

启动 Vibe Coding 控制中心：

```bash
# bin/vibe 已加入 PATH
vibe
```

菜单选项：
- **IGNITION**: 初始化新项目
- **EQUIP**: 安装/更新工具（显示当前版本，支持一键更新）⭐
- **DIAGNOSTICS**: 检查系统状态（显示版本信息和配置状态）⭐

### 快捷命令

安装后可用的快捷命令：

**Claude Code**:
- `c` - 启动 Claude 交互模式
- 单行 prompt：`claude -p "问题"`

**OpenCode**:
- `o` - 启动 OpenCode 交互模式
- 单行 prompt：`opencode run "问题" -m opencode/kimi-k2.5-free`

**其他**:
- `vibe` - 启动控制中心
- `vibe init --ai` - AI 初始化（默认）
- `vibe init --local` - 本地模板初始化
- `vibe chat` / `vc` - 进入默认工具对话

## 新的命令结构

Vibe Coding Control Center 现在采用了 Git 风格的命令架构，提供了更清晰的命令组织：

### 主要命令

- `vibe` - 交互式控制中心
- `vibe chat` - 启动默认 AI 工具聊天
- `vibe equip` - 安装/更新 AI 工具
- `vibe env` - 环境和密钥管理
- `vibe init` - 初始化新项目
- `vibe sync` - 同步工作区身份
- `vibe diagnostics` - 运行系统诊断
- `vibe tdd` - TDD 特性管理
- `vibe help` - 显示帮助信息
- `vibe -h` / `vibe --help` - 显示帮助信息

### 命令特点

1. **模块化设计** - 每个命令都是独立的脚本，便于维护
2. **一致性接口** - 所有命令都支持 `-h/--help` 选项
3. **向后兼容** - 传统的交互式界面仍然可用
4. **易扩展性** - 轻松添加新命令只需创建新的 `vibe-*` 脚本

### 项目初始化

初始化新项目：

```bash
vibe init --ai
vibe init --local
```

将生成并串联：
- `soul.md` / `rules.md` / `agents.md` / `tasks.md`
- `CLAUDE.md`（索引与上下文）
- `.cursor/rules/tech-stack.mdc`

### 更新已安装工具 ⭐ 新功能

更新 Claude Code 或 OpenCode 到最新版本：

```bash
# 方式 1: 使用控制中心（推荐）
./scripts/vibecoding.sh
# 选择 "2) EQUIP"
# 会显示当前版本，选择要更新的工具

# 方式 2: 直接运行安装脚本
./install/install-claude.sh    # 检测到已安装会询问是否更新
./install/install-opencode.sh  # 检测到已安装会询问是否更新
```

更新流程示例：
```
2/6 Check & Update Claude CLI
✓ Claude CLI already installed (version: 2.1.30)
Do you want to update Claude CLI to the latest version? [y/N] y
✓ Updating claude-code via Homebrew...
★ Updated from 2.1.30 to 2.1.31
```

**配置合并**: 更新时会智能合并 MCP 配置，保留你的自定义服务器设置。

## 测试与验证

### 运行完整测试套件

```bash
# 运行所有模块的完整测试
./scripts/test-all.sh
```

### 验证安装

```bash
# 检查系统状态
./scripts/vibecoding.sh
# 选择 "3) DIAGNOSTICS"
```

## 现代化架构特性

### 配置管理
- 集中式配置管理，支持环境特定设置
- 类型安全的配置访问
- 配置验证功能

### 插件系统
- 可扩展的插件架构
- 插件注册和加载机制
- 插件生命周期管理

### 缓存系统
- TTL（Time-To-Live）支持
- 自动过期清理
- 性能优化

### 国际化支持
- 多语言界面
- 动态语言切换
- 本地化消息

### 高级错误处理
- 重试机制（指数退避）
- 断路器模式
- 结构化错误信息

## 安全特性

- **输入验证**: 所有用户输入都经过验证，防止注入攻击
- **路径验证**: 防止目录遍历攻击
- **安全文件操作**: 安全的文件复制和写入函数
- **环境验证**: 检查命令可用性和权限
- **安全用户交互**: 安全的提示和确认函数
- **修复漏洞**: 已修复 prompt_user 函数中的 eval 安全漏洞

## 常见问题

### 故障排除

1. **Claude 无法连接**:
   - 检查 `config/keys.env` 中的 `ANTHROPIC_AUTH_TOKEN`（不是 `ANTHROPIC_API_KEY`）
   - 确认 `ANTHROPIC_BASE_URL` 设置正确

2. **权限错误**: 检查配置文件权限是否正确

3. **缺少依赖**: 确保已安装 Git、Zsh 和 Node.js

4. **API 密钥未加载**: 运行 `source ~/.zshrc`（或你的 shell 配置文件）

5. **MCP 服务器不工作**: 验证 GitHub、Brave Search 等的 API 密钥

6. **环境变量冲突**:
   - 不要混用 `ANTHROPIC_API_KEY` 和 `ANTHROPIC_AUTH_TOKEN`
   - 统一使用 `ANTHROPIC_AUTH_TOKEN`

7. **更新失败**:
   - 确保有网络连接
   - macOS 用户确保 Homebrew 已更新: `brew update`
   - Linux 用户确保 npm 已更新: `npm update -g npm`

8. **MCP 配置被覆盖**:
   - 新版本支持配置合并，更新时选择 "Yes" 合并配置
   - 如果选择了替换，可以从备份文件恢复: `~/.claude.json.backup.*`

9. **安装或更新失败**:
   - 确保 `jq` 已安装 (用于 JSON 操作): `brew install jq` 或 `apt-get install jq`
   - 检查网络连接和防火墙设置

## 开发指南

### 编码规范

- 使用模块化、注释良好的 zsh 脚本，遵循可移植的 shell 实践
- 遵循一致的颜色方案用于用户反馈（在 utils.sh 中定义）
- 实现错误处理使用 `set -e` 实现快速失败
- 将通用函数分离到 `lib/utils.sh` 以供重用
- 使用清晰的变量命名和描述性函数名
- 包含详细注释解释复杂操作
- 对所有用户输入和文件操作实现安全验证
- 对常量和安全参数使用 readonly 变量

### 模块开发

当开发新功能时：

1. 将功能组织到适当的模块中（位于 `lib/` 目录）
2. 确保所有函数都有适当的安全验证
3. 使用现有的日志函数
4. 遵循现有的错误处理模式
5. 为新功能编写测试

### 安全最佳实践

- 始终使用 `validate_input`、`validate_path`、`validate_filename` 验证用户输入
- 使用安全文件操作：`secure_copy`、`secure_write_file`、`secure_append_file`
- 使用 `handle_error` trap 实现适当的错误处理和清理
- 在执行文件操作前始终使用 `validate_path`
- 通过 `prompt_user_safe` 函数处理用户输入，避免使用不安全的 eval

## 项目结构

```
vibe-coding-control-center/
├── CLAUDE.md                    # 项目上下文
├── README.md                    # 本文档
├── MODERN_README.md             # 现代化功能说明（历史文档）
├── CHANGELOG.md                 # 变更日志
├── UPGRADE_FEATURES.md          # 新功能说明（历史文档）
├── config/                      # 配置文件
│   ├── aliases.sh              # 命令别名（动态路径解析）
│   ├── keys.env                # API 密钥（不提交）
│   └── keys.template.env       # 密钥模板
├── docs/                        # 文档
│   ├── agents-guide.md         # Agent 使用指南
│   ├── alias-helper.md         # Worktree/tmux/agent 别名指南
│   ├── usage_advice.md         # 使用建议
│   ├── 技术架构说明.md          # 技术架构
│   └── 项目理解指南.md          # 项目理解
├── install/                     # 安装脚本
│   ├── init-project.sh         # 项目初始化
│   ├── install-claude.sh       # Claude Code 安装
│   └── install-opencode.sh     # OpenCode 安装
├── lib/                         # 共享库
│   ├── utils.sh                # 统一的工具函数库（安全增强）
│   ├── config.sh               # 集中配置管理
│   ├── plugins.sh              # 插件系统
│   ├── cache.sh                # 缓存系统
│   ├── error_handling.sh       # 高级错误处理
│   ├── i18n.sh                # 国际化支持
│   └── testing.sh              # 测试框架
├── scripts/                     # 主要脚本
│   ├── backup-project.sh       # 项目备份
│   ├── vibecoding.sh           # 主控制中心
│   ├── install.sh              # 现代化安装脚本
│   └── test-all.sh             # 完整测试套件
└── tests/                       # 测试
    ├── test_new_features.sh    # 版本检测和更新功能测试
    ├── test_status_display.sh  # 状态显示功能测试
    └── unit/
        ├── simple_test.sh      # 简单测试
        └── test_utils.sh       # 工具函数测试
```

## 重要说明

### Claude Code vs OpenCode

**Claude Code**（官方工具）:
- 官方 Anthropic CLI 工具
- 在中国可通过阿里云兼容端点使用 Qwen 模型
- 需要配置环境变量：`ANTHROPIC_AUTH_TOKEN`、`ANTHROPIC_BASE_URL`、`ANTHROPIC_MODEL`
- 这是一种 workaround（无奈之举）

**OpenCode**（中国原生）:
- 专为中国环境设计
- 原生支持多种模型（Qwen、DeepSeek、Moonshot）
- 无需配置端点和模型，开箱即用
- 这是正道（native solution）

### 环境变量注意事项

⚠️ **重要**: 统一使用 `ANTHROPIC_AUTH_TOKEN`，不要混用 `ANTHROPIC_API_KEY`，避免环境冲突。

## 相关文档

- **[项目理解指南](docs/项目理解指南.md)** - 深入理解项目架构和设计理念
- **[技术架构说明](docs/技术架构说明.md)** - 详细的技术架构文档
- **[使用建议](docs/usage_advice.md)** - 高级使用技巧和最佳实践
- **[Agent 指南](docs/agents-guide.md)** - OpenCode Agent 系统详解

## 贡献

欢迎贡献！请遵循 `CLAUDE.md` 中的编码规范。

## 许可证

本项目开源。详见仓库许可证。
