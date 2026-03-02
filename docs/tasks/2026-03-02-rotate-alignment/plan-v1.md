---
task_id: "2026-03-02-rotate-alignment"
document_type: task-plan
title: "Rotate Workflow Refinement Plan"
author: "Antigravity Agent"
created: "2026-03-02"
last_updated: "2026-03-02"
status: planning
---

# 1. 现状痛点
目前的开发链路是 `start -> ... -> pr`。由于 GitHub 侧采用 Squash 合并策略，PR 合成一个点后，本地发版分支并不知道远端的最新状态，其历史里仍然散落着原本的开发链条。
此时如果不想关闭沙盒（`vibe flow done`），直接拿这个分支继续写，下一个发起的 PR 就会出现大量前一单的祖传 Commit 幽灵。

现存的 `scripts/rotate.sh <new_branch>` 能够强制放弃旧名字旧壳、通过 fetch `origin/main` 产生纯净新分支。
但
1. 它是一个隐形的脚本，普通开发者并不知道可以通过执行这个脚本达到 "原地续命" 的重开效果。
2. 它脱离于当前极智的 `/vibe_xxx` 大盘，旋转完后不会告知 Task Registry 也不会刷新 `.vibe/current-task.json` 挂件。
3. 它仍把“目录名 / branch 名 / task”混成一个概念，没有定义稳定目录与变动任务之间的边界。
4. 它没有系统化的“原地重绑”能力：即保持当前目录不变，但把代码基线、branch、task/worktree 绑定一起切换到新任务。

# 2. 本次明确的用户需求

## 2.1 目录约束
- 默认**不切换目录**。
- 默认**不新建 worktree 目录**。
- 当前 coding agent 的历史对话需要保留，因此新任务应尽量在当前目录原地开始。

## 2.2 状态约束
- rotate 之后，当前目录中的代码必须先与 `origin/main` 一致。
- rotate 之后，当前目录绑定的 `current_task` 必须切换到新任务。
- `.vibe/current-task.json`、`.vibe/focus.md`、`.vibe/session.json` 需要一起刷新。
- 共享 registry/worktree 也要同步切换，不允许“代码已切到新任务，但 task 仍指向旧任务”。

## 2.3 命名约束
当前系统需要明确区分四个概念：

1. **directory / worktree label**：给人看的稳定短名，例如 `refactor`、`bug-fix`
2. **agent**：谁负责该目录，例如 `claude`、`codex`
3. **task_id**：任务注册表的真实任务编号，例如 `2026-03-02-rotate-alignment`
4. **branch**：Git 传输层身份，必须体现 agent 和 task，而不是复用目录短名

推荐命名：
- worktree 目录：`wt-<agent>-<label>`
- branch：`<agent>/<task-id>`

例子：
- 目录：`wt-claude-refactor`
- branch：`claude/2026-03-02-rotate-alignment`
- task：`2026-03-02-rotate-alignment`

目录标签用于“快速识别这个目录大致干什么”，branch 和 task 才表达当前真实工作对象。

# 3. 规划：在现有命令体系上收敛能力

## 环节一：`/vibe-new` 作为唯一智能入口
不新增独立的 `/vibe-rotate`。对用户而言，“在当前目录开新任务”和“在新目录开新任务”都应通过 `/vibe-new` 进入。

Slash 的职责只保留：
- 判断用户是要在当前目录继续，还是新建目录
- 询问最少必要参数（task、agent、是否保留目录）
- 调用底层 shell 命令
- 汇报结果

复杂逻辑不得放在 Slash 内部。

## 环节二：Shell 负责脏活，优先复用现有命令
优先在现有 `vibe new`、`vibe task`、`vibe flow` 上补能力，而不是继续增加新命令。

建议命令边界：
- `vibe new`：任务入口，总控“当前目录开任务 / 新目录开任务”
- `vibe task`：任务配置面，负责 add / update / remove / list
- `vibe flow`：任务流程面，负责 start / review / pr / done

底层可以继续复用 `scripts/rotate.sh` 或其等价 shell 逻辑，但对外不新增新的独立 Slash 概念。

推荐默认行为：
- **当前目录模式**：保持目录路径不变
- **新目录模式**：必要时才创建新 worktree
- **默认对齐主干**：先校验/获取 `origin/main`
- **默认重绑任务**：刷新共享 registry/worktree 与本地 `.vibe/*`
- **默认设置 git identity**：按 agent 生成 `user.name/user.email`

建议保留两个模式，但都由 `/vibe-new` 驱动：

### 模式 A：原地续命（推荐默认）
适用于“PR 已合并，但我不想换目录，只想在当前目录继续下一个任务”。

动作：
1. 校验当前 worktree 是否干净；若不干净则要求显式 `--stash`
2. 校验当前 task 是否已完成或已合并
3. 将当前目录代码重置到 `origin/main`
4. 通过 `vibe task update` 更新 task/worktree 绑定
5. 设置 branch 为新的 `<agent>/<task-id>`
6. 设置 git `user.name=<agent>`、`user.email=<agent>@vibe.coding`
7. 刷新 `.vibe/current-task.json`、`.vibe/focus.md`、`.vibe/session.json`

### 模式 B：显式重开目录（保留兼容）
适用于用户明确要切去另一个 worktree 或重新建目录。

此模式才允许沿用现有 `vibe flow start` 或包装后的 shell 逻辑，但不应作为默认推荐路径。

### 冲突处理建议
- 若当前目录有未提交改动：默认拒绝，或通过 `--stash` 显式保留
- 若当前 branch 尚未合并：默认拒绝做 destructive rotate
- 若目标 branch 已存在于远端：默认拒绝覆盖，除非显式确认
- 若目录标签和 task slug 不一致：允许存在，不视为错误，因为目录标签只是稳定别名
- 若 agent 不在内置白名单（`codex`、`antigravity`、`trae`、`claude`、`opencode`、`kiro`）：默认拒绝，显式 `-f` 才允许写入；强制模式下 email 必须转 slug

## 环节三：`vibe task` 提供最小配置接口
为支撑 `/vibe-new` 和未来的 `/vibe-task`，`vibe task` 应增加最小子命令集：

- `vibe task list`
- `vibe task add`
- `vibe task update`
- `vibe task remove`

其中当前最小必要能力集中在 `update`：
- `--status`
- `--agent`
- `--worktree`
- `--branch`
- `--bind-current`
- `--next-step`

原则：只实现当前场景确实需要的字段，不预铺过度能力。

职责边界再次明确：
- `vibe task` 只处理 task 配置与绑定
- `vibe flow` 只处理流程推进
- `/vibe-new` 只处理入口编排
- 不新增独立的 `/vibe-rotate`

# 4. 对现有 rotate.sh 的修改意见

基于当前脚本行为，建议后续实现时至少做以下改动：

1. **不要再把 branch 名当成 task 名**
   当前 `rotate.sh <new_branch>` 的接口语义太弱，只表达 Git 名字，不表达 task 绑定。

2. **增加原地 rotate 模式**
   当前脚本会切出新 branch，但没有系统性处理 task/worktree 绑定，也没有定义“目录不变”作为正式能力。该能力应被 `/vibe-new` 复用，而不是继续暴露成独立的用户心智模型。

3. **停止依赖目录名推断 feature**
   当前 `lib/flow.sh` 仍通过目录 basename 推断 feature，这会与“稳定目录标签”直接冲突。后续应改为以 registry / `.vibe/current-task.json` 为真源。

4. **增加命名层级**
   branch 负责 Git 身份，目录负责人类识别，task 负责流程与 registry，三者不能继续混用。

5. **补齐冲突策略**
   对 dirty 工作区、未合并分支、已存在远端同名 branch，都要有显式防护。

# 5. 落地实施路线 (To Be Executed)
- **Phase A**: 为 `vibe task` 增加最小 add/update/remove/list 能力。
- **Phase B**: 让 `/vibe-new` 复用 `vibe task` 与现有 shell 逻辑，支持“当前目录开任务 / 新目录开任务”。
- **Phase C**: 清理目录名推断 feature 的旧逻辑，切到“目录标签稳定、task 绑定可变”的模型。
- **Phase D**: 将 agent 对应的 git `user.name/user.email` 写入收敛到同一条 shell 流程里。
