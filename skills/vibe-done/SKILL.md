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
1. 修改 `docs/tasks/<task_id>/README.md`，将 `status:` 变更为 `completed` (或通过用户指定变更为 `archived`、`skipped`)。
2. 修改 `$(git rev-parse --git-common-dir)/vibe/registry.json` 中该 `task_id` 的 `status` 为对应的新状态。

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
