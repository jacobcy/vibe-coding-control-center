# Vibe Coding Control Center - 帮助信息

## 用法

`vibe [选项] [命令]`

## 选项

- `-h, --help` 显示此帮助信息并退出

## 主命令

- `(无参数)` 启动交互式控制中心
- `chat` 快速启动 AI 工具对话
  - `vibe chat` - 启动交互式对话
  - `vibe chat "问题"` - 快速问答（非交互式）
  - `vibe chat skills` - 查看可用技能 (OpenCode)
  - 统一命令接口：自动调用 `claude -p`、`opencode run` 或 `codex exec`
- `config` **AI工具配置管理** (OpenCode, Codex配置文件)
- `doctor` 系统健康检查（包含诊断）
- `env` **环境变量管理** (keys.env, API keys)
- `equip` 安装/更新 AI 工具 (Claude, OpenCode 等)
- `flow` **特性开发工作流** (PRD → 规格 → 测试 → 开发)
- `help` 显示帮助信息
- `init` 启动新项目 (Start New Project)
- `keys` 快速浏览 API keys（`vibe env show` 的别名）

## 环境管理子命令 (vibe env)

管理环境变量配置文件 `~/.vibe/keys.env`：

- `status` 显示环境配置状态（默认）
- `show` 显示 keys.env 内容（带掩码）
- `edit` 编辑 keys.env
- `get <key>` 获取环境变量值
- `set <key> <value>` 设置环境变量
- `sync` 同步项目配置到用户目录
- `detect` 检测和验证环境
- `inject` 导出密钥到当前会话
- `switch <cn|off>` 切换 Claude 端点
- `verify` 验证 API key 有效性

## AI工具配置子命令 (vibe config)

管理 AI 工具的特定配置文件：

- `opencode show`          Display opencode.json
- `opencode edit`          Edit opencode.json
- `codex show`             Display config.toml
- `codex edit`             Edit config.toml
- `codex model [name]`     Get/set Codex model

Examples:
  vibe config                      # Show all config status
  vibe config opencode edit        # Edit OpenCode config
  vibe config codex model          # Show current Codex model
  vibe config codex model gpt-4    # Set Codex model

## 特性开发工作流 (vibe flow)

完整的特性开发生命周期管理，集成现有工具：

- `start <feature> [--agent=claude] [--base=main]`  开始新特性
  - 创建分支和 worktree（通过 `wtnew`）
  - 设置 Git 身份
  - 生成 PRD 模板
  - 初始化工作流状态
  - 可选：创建 tmux 工作区（通过 `vup`）
- `spec [feature]`          编写技术规格
- `test [feature]`          初始化测试 (TDD)
- `dev [feature]`           开发指引（显示 TDD 循环和推荐工具）
- `review [feature]`        代码审核（运行测试 + lazygit）
- `pr [feature]`            创建 Pull Request（通过 gh）
- `done [feature]`          完成并清理（验证 + 归档 + 删除 worktree）
- `status [feature]`        显示工作流状态

**工具集成：**
- `wtnew`/`vup` - Worktree 和 tmux 管理（来自 aliases.sh）
- `gh` - GitHub CLI（PR 管理）
- `lazygit` - 交互式代码审核
- `tmux` - 会话管理

Examples:
  vibe flow start user-auth --agent=claude
  cd ../wt-claude-user-auth
  vibe flow spec
  vibe flow test
  vibe flow dev
  vibe flow review
  vibe flow pr
  vibe flow done



## 配置文件位置

**环境变量 (vibe env 管理):**
- `~/.vibe/keys.env` - API 密钥和环境变量

**AI工具配置 (vibe config 管理):**
- `~/.config/opencode/opencode.json` - OpenCode 配置
- `~/.codex/config.toml` - Codex 配置

**其他:**
- `~/.vibe/aliases.sh` - 命令别名
- `~/.claude.json` - MCP 服务器配置

## 快捷别名

- `vibe` 启动控制中心
- `vc` 进入默认 AI 工具对话
- `c` Claude Code
- `o` OpenCode
- `vnew` 创建新的工作区
- `wt` 切换工作树

更多信息请访问: https://github.com/affaan-m/vibe-coding-control-center
