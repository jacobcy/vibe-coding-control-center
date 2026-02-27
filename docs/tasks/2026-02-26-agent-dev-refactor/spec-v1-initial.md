# 技术规格：Agent 开发方向（文档阶段）

## 目的
为 Vibe Coding 的 Agent 工具链重构提供明确的技术方向与边界。当前阶段仅文档定义，不包含代码改动。

## 总体目标
- **多工具协作**：Claude → OpenCode → Codex 按优先级组织。
- **中国环境默认可用**：Claude 默认通过中转站 `https://api.myprovider.com  # 替换成你的中转站`，无需本机代理。
- **环境变量一键切换**：基于 `config/keys.env` 与 alias 实现快速切换。
- **Worktree 隔离**：每个 agent 独立 worktree + 独立 Git 身份。
- **会话稳定**：tmux 保持会话，lazygit 负责审查。
- **TDD 流程**：PRD → 技术规格 → 测试文档 → 测试代码 → 正式代码 → Review → PR。

## Agent 工具链设计
### 1) 优先级与使用策略
- **优先级**：Claude（首选）→ OpenCode（补位）→ Codex（第三优先级）
- **启用方式**：通过 alias 启动，并加载对应环境变量

### 2) Claude（中国默认）
- 默认端点：`https://api.myprovider.com  # 替换成你的中转站`
- 官方端点：`https://api.anthropic.com`
- 切换方式：alias 或环境变量覆盖

### 3) OpenCode
- 原生支持多模型（Qwen / DeepSeek / Moonshot）
- 通过 API Key 启用对应模型能力

### 4) Codex
- 作为第三优先级工具启用
- 默认不影响 Claude / OpenCode 的配置

## 环境变量规范（目标态）
### Claude
- `ANTHROPIC_AUTH_TOKEN`
- `ANTHROPIC_BASE_URL`
- `ANTHROPIC_MODEL`

### OpenCode（可选）
- `DEEPSEEK_API_KEY`
- `MOONSHOT_API_KEY`

### Codex（可选）
- 由 Codex CLI 自身环境变量控制（后续补充）

## Worktree 与身份隔离
- 每个 agent 对应一个 worktree
- worktree 中设置独立 Git identity（user.name / user.email）
- 通过 alias 统一创建 / 切换 / 启动

## 依赖与工具链
- 必须依赖：`git` `tmux` `lazygit` `zsh`
- 安装检测与提示应在文档与 CLI 中同步（后续实现）

## 文档与仓库结构
- `docs/` 仅放“给人读”的文档
- Agent 使用说明与仓库规则留在根目录（`README.md` / `CLAUDE.md` / `SOUL.md`）

## 交付物清单（当前阶段）
- 技术规格文档（本文件）
- PRD 文档
- 测试文档

## 非目标
- 不修改现有脚本与逻辑
- 不引入新的依赖安装流程
- 不实施任何 alias 或配置改动

