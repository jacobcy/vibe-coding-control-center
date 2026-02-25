# Tasks: fix-alias-bugs

## 任务清单

### 任务 1: 修复 wt 命令路径解析
- [x] 修改 `config/aliases/worktree.sh` 中的 `wt()` 函数
- [x] 使用 `git worktree list --porcelain` 获取准确路径
- [x] 验证语法正确：`zsh -n config/aliases/worktree.sh`

### 任务 2: 修复 vtls 变量名冲突
- [x] 修改 `config/aliases/tmux.sh` 中的 `vtls()` 函数
- [x] 将 `status` 改为 `status_icon`
- [x] 验证语法正确：`zsh -n config/aliases/tmux.sh`

### 任务 3: 验证修复
- [ ] 在新 shell 中测试 `wt` 命令切换 worktree
- [ ] 在新 shell 中测试 `vtls` 命令显示 session 列表
- [ ] 验证无变量名冲突错误

## 依赖关系

- 任务 1 和任务 2 可并行执行
- 任务 3 依赖任务 1 和任务 2 完成

## 回滚计划

如需回滚：
```bash
git checkout HEAD -- config/aliases/worktree.sh config/aliases/tmux.sh
source ~/.zshrc
```
