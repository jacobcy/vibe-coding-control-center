# Spec: tmux-session-management

## Requirements

### REQ-001: vtls 命令无错误执行
- **Given**: 用户执行 `vtls`
- **When**: 命令执行
- **Then**: 正常显示 tmux session 列表，无变量名冲突错误

### REQ-002: vtls 显示 session 状态
- **Given**: 存在活动的 tmux sessions
- **When**: 执行 `vtls`
- **Then**: 正确显示 session 名称、窗口数量和连接状态

## Design Notes

- 避免使用 zsh 保留变量名（如 `status`）
- 使用 `status_icon` 替代 `status` 作为变量名
