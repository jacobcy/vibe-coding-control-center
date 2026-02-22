# Claude Code Usage

## Summary
Claude Code 并行开发工作流的事实核查与最佳实践。验证了 Claude Code 没有原生的 teammate 模式或 --worktree/--tmux 标志，项目封装的 wtnew/vup/vnew 是正确的解决方案。

## Key Decisions
- Claude Code 没有原生 `--worktree` 标志 - 需要手动 `git worktree add`
- Claude Code 没有原生 `--tmux` 标志 - 需要手动用 tmux 管理
- Claude Code 没有 "Teammate Mode" - 这是虚构的功能
- `--agents` 参数用于定义 agent prompt，而非并行运行多个 agent
- Task 工具用于在当前 session 调用子 agent，非独立 tmux pane

## Problems & Solutions
### 错误的教程信息
- **Issue**: 网络教程声称 Claude Code 有 `--worktree`, `--tmux`, `--teammate-mode` 等原生支持
- **Solution**: 经过官方文档搜索和 CLI 测试，确认为虚假信息
- **Lesson**: 需要从官方文档或实际测试获取信息，不能轻信教程

### tmux 结构理解
- **Issue**: 不理解 tmux session/window/pane 的层级关系
- **Solution**:
  - session = 一个 tmux 会话
  - window = 相当于标签页
  - pane = 实际的分屏
  - 命令: `tmux ls`, `tmux list-windows`, `tmux list-panes`

### 封装的正确性
- **Issue**: 质疑项目的 wtnew/vup/vnew 组合是否是最优方案
- **Solution**: 确认这是 2026 年能实现的**最自动化**方案，等同于终端版 VS Code 多 workspace
- **Lesson**: 手动创建 worktree → 手动 tmux 开窗口 → 手动启动 Claude 是唯一正确流程

## Related Tasks
- [ ] claude-20260222-001: 整理 Claude Code 最佳实践文档

## References
- `config/aliases.sh` - wtnew, vup, vnew 实现
- Claude Code CLI: `claude --help`
- `/learn-claude-code-worktrees` - 官方的 worktree 教程

---
Created: 2026-02-22
Last Updated: 2026-02-22
Sessions: 1
