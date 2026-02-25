# Problem: 别名系统路径解析和变量名冲突

## 问题概述

别名系统中有两个关键 bug 需要修复：

1. **wt 命令路径解析错误** - 无法正确切换到 worktree 目录
2. **vtls 命令变量名冲突** - 使用了 zsh 保留变量名 `status`

## 问题详情

### 1. wt 命令路径解析错误

**现象**：
- 用户创建 worktree 后，无法通过 `wt <name>` 切换到该 worktree
- 命令尝试进入错误的路径，导致 "no such file or directory" 错误

**错误示例**：
```
➜  wt-claude-refactor git:(refactor) wt refactor
wt:cd:10: no such file or directory: /Users/jacobcy/src/vibe-center/main/refactor

➜  wt-claude-refactor git:(refactor) wt wt-claude-refactor
wt:cd:10: no such file or directory: /Users/jacobcy/src/vibe-center/main/wt-claude-refactor

➜  wt-claude-refactor git:(refactor) wt main
wt:cd:10: no such file or directory: /Users/jacobcy/src/vibe-center/main/main
```

**根本原因**：
- 当前实现假设 worktree 在 `$VIBE_REPO/$target` 下
- 实际 worktree 在 repo 的父目录中（如 `../wt-claude-refactor`）
- 没有使用 `git worktree list` 来获取准确路径

### 2. vtls 命令变量名冲突

**现象**：
- 运行 `vtls` 时报错：`vtls:18: read-only variable: status`

**根本原因**：
- `status` 是 zsh 的保留/只读变量
- 代码中使用了 `local status=...` 导致冲突

**当前问题代码**（config/aliases/tmux.sh:144）：
```zsh
local status="${attached:+✓ (attached)}"
```

## 影响

1. **用户无法高效切换 worktree** - 降低了工作流效率
2. **无法查看 tmux session 列表** - 影响 tmux 工作流
3. **用户体验不一致** - 某些命令工作正常，某些失败

## 复现步骤

### wt 问题：
1. 在 vibe-center/main 目录下
2. 运行 `wtnew refactor` 创建 worktree
3. 运行 `wt refactor` 尝试切换
4. 观察到路径错误

### vtls 问题：
1. 运行 `vtls`
2. 观察到 `read-only variable: status` 错误
