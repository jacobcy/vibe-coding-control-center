## Why

别名系统存在两个关键 bug 影响日常使用：
1. `wt` 命令无法正确切换到 worktree 目录，路径解析逻辑错误
2. `vtls` 命令使用 zsh 保留变量名 `status`，导致运行时错误

这些 bug 阻碍了 worktree 工作流的正常使用，需要立即修复。

## What Changes

- **修复 `wt` 命令路径解析**：使用 `git worktree list` 获取准确路径，替代错误的本地路径推断
- **修复 `vtls` 变量名冲突**：将 `status` 改为 `status_icon`，避免与 zsh 保留变量冲突

## Capabilities

### New Capabilities
- (无新功能，仅修复现有功能)

### Modified Capabilities
- worktree-navigation: 修复 `wt` 命令的路径解析逻辑
- tmux-session-management: 修复 `vtls` 命令的变量名冲突

## Impact

- 文件：`config/aliases/worktree.sh`, `config/aliases/tmux.sh`
- 无 API 变更，无依赖变更
- 向后兼容：修复后的命令行为与预期一致
