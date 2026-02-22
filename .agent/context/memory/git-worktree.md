# Git Worktree 最佳实践

## Summary
Vibe Coding 环境下使用 Git Worktree 进行多任务并行开发的最佳实践流程，涵盖分支合并、PR 提交流程。

## Key Decisions
- **PR 方式优先**: 采用 PR 方式合并分支，而非直接 push（便于代码审查）
- **先 PR 后本地**: 本地 main 有未 push 提交时，先合并 PR，再 push 本地提交（保持历史干净）
- **Feature 分支 rebase**: 在 feature 分支上 rebase origin/main 同步最新代码

## Problems & Solutions
### Worktree 下无法切换分支
- **Issue**: Agent 无法在同一个会话中切换工作目录
- **Solution**: 通过 PR 连接不同 worktree 的工作
- **Lesson**: 开发在 feature worktree，审核在 main worktree

### 本地 main 领先 origin/main
- **Issue**: 本地 main 有未 push 的提交，origin/main 也有新提交
- **Solution**: 先合并 PR 到 origin/main，再 pull + push 本地提交
- **Lesson**: 不需要在 feature 分支 rebase 本地 main，保留完整历史

### Force push 风险
- **Issue**: rebase 会改变分支历史，需要 force push
- **Solution**: 单人开发分支可安全使用 force push，团队分支用 merge
- **Lesson**: 根据协作人数选择合并策略

### Rebase vs Merge 选择
- **Rebase**: 产生线性历史，适合单人分支
- **Merge**: 保留完整分支历史，适合团队协作
- **选择依据**: 团队规模 + 历史偏好

## Related Tasks
- [ ] worktree-20260222-001: 整理完整 Worktree 工作流文档
- [x] worktree-20260222-002: 验证 PR + 本地提交流程

## References
- [git-worktree(1)](https://git-scm.com/docs/git-worktree)
- [Git 分支合并策略](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/incorporating-ch-pull-request/about-pull-request-meranges-from-ages)

---
Created: 2026-02-22
Last Updated: 2026-02-22
Sessions: 1
