# Vibe Coding Control Center - 帮助信息

## 用法

`vibe [选项] [命令]`

## 选项

- `-h, --help` 显示此帮助信息并退出

## 主命令

- `(无参数)` 启动交互式控制中心
- `chat` 启动默认 AI 工具对话模式
- `config` 配置管理
- `equip` 安装/更新 AI 工具 (Claude, OpenCode 等)
- `env` 环境与密钥管理
- `help` 显示帮助信息
- `init` 初始化新项目
- `keys` API 密钥管理（`vibe env keys` 的快速入口）
- `sync` 同步工作区身份
- `doctor` 系统健康检查（包含诊断）
- `tdd` TDD 功能管理

## 环境管理子命令 (vibe env)

- `status` 显示环境配置状态
- `detect` 检测和验证环境
- `setup` 交互式环境设置
- `inject` 导出密钥到当前会话
- `switch <cn|off>` 切换 Claude 端点
- `keys show|edit|verify` 密钥管理
- `mcp` 配置 MCP 服务器

## 配置文件位置

- `~/.vibe/keys.env` - API 密钥配置
- `~/.vibe/aliases.sh` - 命令别名
- `~/.config/opencode/opencode.json` - OpenCode 配置
- `~/.codex/config.toml` - Codex 配置
- `~/.claude.json` - MCP 服务器配置

## 快捷别名

- `vibe` 启动控制中心
- `vc` 进入默认 AI 工具对话
- `c` Claude Code
- `o` OpenCode
- `vnew` 创建新的工作区
- `wt` 切换工作树

更多信息请访问: https://github.com/affaan-m/vibe-coding-control-center
