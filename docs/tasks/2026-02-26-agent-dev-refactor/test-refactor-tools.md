# 测试文档：多工具链重构（Claude / OpenCode / Codex）

## 测试范围
本测试文档覆盖“目标态”设计的验证点。当前阶段不写测试代码，仅定义测试计划与用例。

## 测试分类
1. **配置与环境变量测试**
2. **工具启动与优先级测试**
3. **worktree 与身份隔离测试**
4. **依赖与会话测试**

## 关键用例（示例）
### A. 配置与环境变量
- A1：默认环境下，Claude 使用 `ANTHROPIC_BASE_URL=https://api.myprovider.com  # 替换成你的中转站`
- A2：切换 alias 后，Claude 使用 `https://api.anthropic.com`
- A3：`config/keys.env` 变更后，alias 启动生效

### B. 工具启动与优先级
- B1：优先级 Claude → OpenCode → Codex 的启动顺序符合预期
- B2：未安装的工具被跳过并提示
- B3：Codex 在配置开启时可正常启动

### C. Worktree 与身份隔离
- C1：在 `wt-claude-*` 中提交，Git user.name 为 claude
- C2：在 `wt-opencode-*` 中提交，Git user.name 为 opencode
- C3：在 `wt-codex-*` 中提交，Git user.name 为 codex

### D. 依赖与会话
- D1：缺少 tmux 时提示安装
- D2：tmux 会话断线后可恢复
- D3：lazygit 可正常监控改动

## 退出标准
- 所有关键用例通过
- 文档与实现一致

