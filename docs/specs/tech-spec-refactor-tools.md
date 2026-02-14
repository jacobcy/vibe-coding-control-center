# 技术规格：多工具链重构（Claude / OpenCode / Codex）

## 概述
本技术规格描述目标态的工具链结构、配置方案与环境变量管理策略。当前阶段不实现代码，仅定义规范。

## 目标架构（目标态）
- **工具顺序**：Claude → OpenCode → Codex
- **工作区隔离**：每个 agent 在独立 worktree 内运行
- **身份标识**：每个 worktree 设定独立 Git user.name/user.email
- **会话保障**：tmux 保持长期会话，lazygit 负责审查

## 环境变量与配置
### 1) 统一配置来源
- 主配置文件：`config/keys.env`
- 通过 alias 快速切换工具所需变量

### 2) Claude 变量规范
- `ANTHROPIC_AUTH_TOKEN`
- `ANTHROPIC_BASE_URL`
- `ANTHROPIC_MODEL`

### 3) Claude 中国默认端点
- 默认：`https://api.myprovider.com  # 替换成你的中转站`
- 通过 alias/环境切换为官方：`https://api.anthropic.com`

### 4) OpenCode / Codex
- OpenCode 使用其官方 CLI 与可选 API Key
- Codex 作为第三优先级工具（可选启用）

## Worktree 规则（目标态）
- worktree 命名体现 agent 类型（如 `wt-claude-*` / `wt-opencode-*` / `wt-codex-*`）
- 每个 worktree 设置独立 Git user.name/user.email
- alias 负责启动对应 agent 与环境变量

## 依赖要求（目标态）
- `git` / `tmux` / `lazygit` / `zsh`
- 需要文档化依赖检测与安装入口

## 文档与文件结构调整建议
- `docs/` 保持“给人阅读的文档”
- agent 使用的文档保留在仓库根目录（如 `CLAUDE.md` / `SOUL.md`）
- `docs/locales/` 属于运行时数据，后续可考虑迁移至 `config/` 或 `assets/`（需代码配合）

## 不在本阶段实现的内容
- 实际 alias 脚本改动
- 自动安装依赖逻辑
- CLI 行为变更

