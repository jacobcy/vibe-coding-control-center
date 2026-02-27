# 测试文档：Agent 开发方向（文档阶段）

## 目标
覆盖 Agent 工具链重构的关键验证点。当前阶段不写测试代码，仅定义测试计划与用例。

## 测试范围
- 环境变量切换
- 工具优先级
- worktree 身份隔离
- tmux/lazygit 依赖与会话稳定

## 用例清单
### 环境变量
- A1：默认 Claude 端点为 `https://api.myprovider.com  # 替换成你的中转站`
- A2：切换 alias 后 Claude 使用官方端点
- A3：`config/keys.env` 更新后 alias 生效

### 工具优先级
- B1：Claude 优先启动
- B2：Claude 不可用时切换 OpenCode
- B3：Codex 作为第三优先级补位

### Worktree 身份隔离
- C1：`wt-claude-*` user.name=claude
- C2：`wt-opencode-*` user.name=opencode
- C3：`wt-codex-*` user.name=codex

### 依赖与会话
- D1：缺少 tmux 时提示安装
- D2：tmux 会话断线可恢复
- D3：lazygit 正常监控改动

## 退出标准
- 关键用例覆盖完整
- 文档与技术规格一致

