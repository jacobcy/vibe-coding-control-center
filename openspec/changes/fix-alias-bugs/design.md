# Design: 别名系统 Bug 修复

## 设计原则

1. **简单可靠** - 使用 git 提供的准确信息，而非推断
2. **最小改动** - 只修复 bug，不引入新功能
3. **向后兼容** - 保持现有命令行为不变

## 修复方案

### 1. wt 命令路径解析修复

**当前问题**：
- 使用 `$VIBE_REPO/$target` 推断路径
- worktree 实际位于 repo 的父目录中

**解决方案**：
- 使用 `git worktree list` 获取准确路径
- 通过 worktree 目录名匹配用户输入
- 支持通过完整路径或目录名切换

**新实现**（伪代码）：
```zsh
wt() {
  local target="$1"

  # 无参数 = 列出 worktrees
  if [[ -z "$target" ]]; then
    git worktree list
    return
  fi

  # 从 git worktree list 中查找匹配的路径
  local wt_path
  wt_path=$(git worktree list --porcelain |
    awk -v name="$target" '
      /^worktree / {
        path = substr($0, 10)
        basename = path
        sub(/.*\//, "", basename)
        if (basename == name || path == name) {
          print path
          exit
        }
      }
    ')

  if [[ -n "$wt_path" && -d "$wt_path" ]]; then
    cd "$wt_path"
  else
    echo "Worktree not found: $target"
    return 1
  fi
}
```

**优势**：
1. 路径总是准确的（来自 git）
2. 代码更简单，没有复杂的路径推断
3. 支持通过目录名或完整路径切换

### 2. vtls 变量名冲突修复

**当前问题**：
```zsh
local status="${attached:+✓ (attached)}"  # 错误：status 是保留字
```

**解决方案**：
```zsh
local status_icon="${attached:+✓ (attached)}"  # 使用非保留字变量名
```

**影响范围**：
- 仅修改 `config/aliases/tmux.sh` 第 144 行
- 不影响任何其他功能

## 文件变更清单

| 文件 | 变更类型 | 变更内容 |
|------|----------|----------|
| `config/aliases/worktree.sh` | 修改 | 重写 `wt()` 函数，使用 `git worktree list` 获取路径 |
| `config/aliases/tmux.sh` | 修改 | 第 144 行，`status` → `status_icon` |

## 测试计划

1. **wt 命令测试**：
   ```zsh
   wtnew test-branch
   wt wt-claude-test-branch  # 应成功切换
   wt  # 应列出所有 worktrees
   cd /path/to/main && wt wt-claude-test-branch  # 从任何地方都应工作
   ```

2. **vtls 命令测试**：
   ```zsh
   vtup test-session
   vtls  # 应无错误地显示 session 列表
   ```

## 回滚计划

如果出现问题：
1. 从 git 恢复原始文件
2. 重新加载 shell 配置：`source ~/.zshrc`
