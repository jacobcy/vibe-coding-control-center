# PRD：多工具链重构（Claude / OpenCode / Codex）

## 背景与目标
Vibe Coding 的目标是打造一个方便快捷的 Vibe Coding 开发环境，提供跨工具、跨环境的一致体验。本次重构聚焦在：
- 同时支持 Claude、OpenCode、Codex 三类工具
- 通过环境变量与别名一键切换工具配置
- 中国环境下默认使用 Claude API 中转站（无需本机代理）
- 结合 git worktree 为不同 agent 建立独立工作区与身份配置

## 目标（Goals）
1. **多工具链统一入口**：按照优先级 Claude → OpenCode → Codex 组织使用方式。
2. **环境变量一键切换**：基于 `config/keys.env` 与别名，实现工具级别的快速切换。
3. **中国环境默认可用**：Claude 默认指向中转站 `api.myprovider.com  # 替换成你的中转站`，并可切换到官方端点。
4. **工作区隔离**：为不同 agent 设定独立 worktree、目录与 Git 身份（如 user.name）。
5. **开发流标准化**：采用 TDD 工作模式（PRD → 技术规格 → 测试文档 → 测试 → 代码 → Review → PR）。

## 非目标（Non-goals）
- 不在此阶段实现具体代码重构与脚本改动。
- 不引入新的依赖安装逻辑（仅记录规划）。
- 不调整现有 CLI 行为（仅在文档中定义目标态）。

## 用户画像
- 需要在多环境切换的开发者（国内/海外）
- 多 agent 并行协作的工程师（Claude / OpenCode / Codex）
- 依赖 tmux / git worktree / lazygit 的重度 CLI 用户

## 使用场景（User Stories）
1. 作为中国用户，我希望 Claude 默认走中转站，不配置代理即可使用。
2. 作为多 agent 使用者，我希望每个 worktree 有自己的 Git 身份，避免提交混淆。
3. 作为日常使用者，我希望通过 alias 一键切换工具的环境变量与启动方式。
4. 作为远程开发者，我希望 tmux 保持会话，SSH 断线后仍可继续。
5. 作为 reviewer，我希望用 lazygit 快速查看改动与提交。

## 需求（Requirements）
- 环境变量管理基于 `config/keys.env`，并支持 alias 切换不同配置。
- Claude 中国默认端点为 `https://api.myprovider.com  # 替换成你的中转站`（可切换到官方端点）。
- 三类工具按优先级组织，启动方式统一、可预配置。
- 每个 worktree 可设置 Git user.name/user.email 来标识 agent。
- 依赖检测（tmux / lazygit / git / zsh）需要文档化并规划自动化检查。

## 验收标准（Acceptance Criteria）
- 文档清晰定义目标架构与配置方式。
- PRD / 技术规格 / 测试文档齐全并互相一致。
- 不触发实际代码变更（本阶段仅文档）。

## 风险与依赖
- 中转站可用性与稳定性依赖外部服务。
- 多工具环境变量切换易产生冲突，需要明确分层与命名约定。
- worktree 身份管理需要与现有工作流保持兼容。

## 里程碑
1. 文档准备（当前阶段）
2. 技术规格确认
3. 测试文档与用例
4. 实施与重构
5. Review 与 PR
