# PRD：Agent 开发方向（文档阶段）

## 背景
Vibe Coding 希望提供一个方便快捷的 Vibe Coding 开发环境，支持多工具协作、跨环境切换与稳定的远程工作体验。本 PRD 定义 Agent 工具链重构的产品方向与目标。

## 目标
1. **多工具协作**：Claude → OpenCode → Codex 优先级明确，统一入口。
2. **中国环境默认可用**：Claude 默认走中转站 `https://api.myprovider.com  # 替换成你的中转站`。
3. **环境变量一键切换**：通过 `config/keys.env` 与 alias 完成切换。
4. **Worktree 隔离**：每个 agent 独立 worktree + Git 身份。
5. **稳定会话**：依赖 tmux，lazygit 做审查。
6. **TDD 流程落地**：先文档，再测试，再代码。

## 非目标
- 本阶段不做任何代码改动或脚本改动。
- 不新增依赖安装逻辑。

## 用户画像
- 多 agent 并行开发者
- 中国环境下使用 Claude 的用户
- 依赖 tmux / lazygit 的远程协作者

## 关键场景
1. 在中国环境，Claude 默认直接可用，无需本机代理。
2. 在不同 worktree 中提交，Git 身份自动区分 agent。
3. 通过 alias 一键切换 Claude/OpenCode/Codex。

## 需求清单
- 工具优先级：Claude → OpenCode → Codex
- 中转站默认端点：`https://api.myprovider.com  # 替换成你的中转站`
- 环境变量统一管理：`config/keys.env`
- Worktree 身份隔离：user.name / user.email
- 依赖可用性检查：git / tmux / lazygit / zsh

## 验收标准
- 文档明确、可执行且一致
- PRD / 技术规格 / 测试文档互相对齐

