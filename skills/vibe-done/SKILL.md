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

作为整个开发闭环的最后一扣，`/vibe-done` 只做一件事：**任务结算与大盘清理**。
`/vibe-done` 是 skill 层入口；`vibe flow done`、`vibe task update` 是 shell 层工具。在执行 `vibe flow done` 前后，用户通常需要呼叫本指令通知 AI 结算任务。

**命令自检:** 对 `vibe flow`、`vibe task` 或 `git` 的参数有任何不确定时，先运行对应命令的 `-h` / `--help`。shell 命令是 agent 的执行工具，不是给用户背诵的命令列表。

## Workflow Steps

### Step 1: 读取环境与上下文
1. 首先识别当前目录是否有 `.vibe/current-task.json`，若有，从中提取 `task_id`。
   - 如果不存在该文件，则询问用户需要结算的任务编号。
2. 根据目标 `task_id` 加载 `docs/tasks/<task_id>/README.md` 与 `$(git rev-parse --git-common-dir)/vibe/registry.json`，确保数据存在。

### Step 0: Shell-Level Cleanup
 
 ```bash
 vibe flow done
 ```
 
 运行 `vibe flow done` 来标记任务结束、冻结代码、并自动清理本地与远程分支及 Worktree。
 
 ### Step 1: 标记任务状态进度

> ⚠️ **收口边界绝杀原则（必须严格遵守）**：`/vibe-done` 是一个 **Post-PR 的终结级别元数据清算指令**。
> - **【红线】绝对禁止修改任何业务源代码文件！** 任务此时已实质结束（可能已合并），任何试图在这里再动代码的行为都会导致无限 PR 循环。如果检查时发现代码遗留 Bug，请**直接报错并停止**，让用户新开 Task，绝不允许你擅自进行二次修复代码及提交！
> - **共享状态写入只能通过 shell API 完成**，例如 `vibe task update ...`、`vibe flow done`。skill 可以读取 `.git/vibe/*` 状态并解释，但不得手工直接编辑真源 JSON。
> - **严禁修改 `docs/` 等项目内文档**。追踪大盘数据应全部收敛在 `.git/vibe/` 内。

1. **审计追责 (Accountability)**：你必须首先清楚自己作为当前正在运行的 AI 的真实身份。然后通过 `git config user.name` 检查当前沙盒中记录的签名身份是否匹配你的真实身份。如果环境显示的是别人的名字（或者未设置），你应先使用 `wtinit <你自己的名字>` 进行修正，然后再以你的真实身份作为**“结项操作者”**进行记录。
2. **调用 `vibe task update <task_id> --status completed --unassign`**：通过 shell API 将该任务设为 `completed` 并解除现场绑定；若要归档，再显式调用支持的 shell 命令，不要口头发明状态值。
### Step 2: 归档合规与防丢代码检查

**强制审查点：** 
1. 你的职责是在发起清除前，使用 Git 状态和 PR 状态判断是否有未提交 (uncommitted) 或未合并 (unmerged) 到 `origin/main` 的代码。
2. 确认版本升级和 `CHANGELOG.md` 已在 `vibe flow pr` 阶段通过 `--bump` 完成。如果并未进行版本升级，且这是个功能交付，应提醒用户补做（即先运行 `/vibe-commit` 生成 commit，然后运行 `vibe flow pr` 提交 PR）。
3. 如果检查到有遗留代码或任务没有走到终点，**严重警告用户潜在的数据丢失风险**，并拒绝往下执行。

### Step 3: 工作区本地清理（Optional）
如果用户当前处于安全通过检查的状态，询问用户是否要自动一并运行 `vibe flow done` 控制台命令为您把此工作树文件直接抹除回主树：
- 该命令 (`vibe flow done`) 本身已经内涵了安全检测逻辑。当你调用它时，如果发现未 Clean 或未 Merge，它也会执行二次阻断。

### Step 3: 输出封板报告
在聊天界面打印封板小结：
```markdown
🎉 **任务结算完毕！**

• **已锁定任务:** <Task_ID: Title>
• **更新状态:** 从 `in_progress` -> `completed`
• **结项操作者:** <Agent_Name>
• **大盘注册表:** 共享状态库已同步清理。

若还需要开始新探索，请 `vibe-new <feature>`。
```
