---
name: vibe-done
description: 提交 PR 或结束本地工作树后用于收尾工作，一键流转到 Completed/Archived 状态，并强制将状态刷入全局 Registry 和工作树列表缓存。
trigger: manual
enforcement: hard
phase: ending
input_examples:
  - prompt: "我要收口并完成当前任务"
    call: "vibe-done"
---

# Vibe Done Skill

作为整个开发闭环的最后一扣，本指令只做一件事：**任务结算与大盘清理**。
在执行 `vibe flow done` (CLI 移除工作树) 前后，用户通常需要呼叫本指令通知 AI 结算任务。

## Workflow Steps

### Step 1: 读取环境与上下文
1. 首先识别当前目录是否有 `.vibe/current-task.json`，若有，从中提取 `task_id`。
   - 如果不存在该文件，则询问用户需要结算的任务编号。
2. 根据目标 `task_id` 加载 `docs/tasks/<task_id>/README.md` 与 `$(git rev-parse --git-common-dir)/vibe/registry.json`，确保数据存在。

### Step 2: 更新任务进度

> ⚠️ **收口边界原则（必须严格遵守）**：`/vibe-done` 是一个 **Post-PR 的元数据清算指令**。
> - **只写 `.git/vibe/` 目录下的 JSON 文件**（registry.json、worktrees.json）。这些文件在 `.git/` 里，不被 Git 追踪，修改它们不会产生新的 dirty 文件或 commit。
> - **严禁修改 `docs/tasks/<task_id>/README.md`**。Task README 里的 `status` 字段是开发阶段的产物，必须在 PR 合并之前作为 commit 的一部分提交进去。如果在收口时修改它，会产生新 dirty 文件、需要新 commit、触发新 PR——陷入无法收口的死循环。
> - 如果发现 README 里的状态还没有更新为 `completed`，应**提醒用户**在合并前补上这个 commit，而不是在这里替他修改。

1. **检查 `docs/tasks/<task_id>/README.md` 的 status 字段（只读）**：
   - 若已是 `completed`，继续下一步。
   - 若仍是 `in_progress`，**警告用户**："该任务的 README status 尚未标记为 completed，建议在 PR 合并前补一个 commit 更新它，否则文档状态将与大盘不一致。继续收口吗？"
2. **写入 `$(git rev-parse --git-common-dir)/vibe/registry.json`**：将该 `task_id` 的 `status` 更新为用户选择的新状态（`completed` / `archived` / `skipped`）。

### Step 3: 更新全局 Worktrees Map
修改 `$(git rev-parse --git-common-dir)/vibe/worktrees.json`:
- 查找当前所在的 `worktree_name`（或被传入 `current_task` 匹配的节点）。
- 如果当前已经在 CLI 层执行了 `done`，该 worktree 可能已经准备删掉，这儿你需要：
   - 将这棵树的状态标记为 `idle` 甚至直接从 `worktrees` 数组中移除该条目，防止未来显示为幽灵僵尸。

### Step 4: 工作区本地清理（Optional）
询问用户是否要自动一并运行 `vibe flow done` 控制台命令为您把此工作树文件直接抹除回主树：
- 这只在你发现当前 CLI 端还没有物理清理工作树时提供。

### Step 5: 输出封板报告
在聊天界面打印封板小结：
```markdown
🎉 **任务结算完毕！**

• **已锁定任务:** <Task_ID: Title>
• **更新状态:** 从 `in_progress` -> `completed`
• **大盘注册表:** 共享状态库已同步清理。

若还需要开始新探索，请 `vibe-new <feature>`。
```
