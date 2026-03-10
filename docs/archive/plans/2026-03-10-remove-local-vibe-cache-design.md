---
title: "Remove Local .vibe Cache Design"
date: "2026-03-10"
status: "draft"
author: "GPT-5.4"
related_docs:
  - docs/standards/shell-capability-design.md
  - docs/standards/git-workflow-standard.md
  - docs/standards/glossary.md
  - docs/tasks/2026-03-10-continue-save-start-audit/README.md
  - docs/tasks/2026-03-10-continue-save-start-audit/findings-2026-03-10.md
  - lib/task_write.sh
  - lib/task_query.sh
  - lib/task_actions.sh
  - lib/task.sh
  - skills/vibe-save/SKILL.md
  - skills/vibe-continue/SKILL.md
  - .agent/workflows/vibe-start.md
  - STRUCTURE.md
  - tests/test_task_ops.bats
---

# Remove Local .vibe Cache Design

## Goal

移除 worktree 本地 `.vibe/` 作为运行时缓存和任务指针层的语义，让 `vibe task (shell)`、`vibe flow (shell)` 与相关 skill/workflow 只依赖共享真源和本地 handoff。

本轮设计要明确保留两条边界：

1. `~/.vibe/` 继续承担全局配置、loader、keys、skills 偏好等跨仓库语义。
2. `.agent/context/task.md` 继续只做人类 handoff，不升级为 shell 查询真源。

## Non-Goals

- 不移除或重命名 `~/.vibe/` 下的全局配置结构。
- 不把 `.agent/context/task.md` 改造成结构化 registry 或 shell 数据入口。
- 不在本轮重做 task/flow 的整体模型；只删除 worktree 本地 `.vibe/` 冗余层并同步边界文档。
- 不引入新的本地替代缓存文件来接替 `.vibe/current-task.json`、`.vibe/focus.md`、`.vibe/session.json`。

## Context

当前仓库同时存在两种 `.vibe`：

1. `~/.vibe/`
   - 用于全局安装、loader、keys、skills 配置。
   - 这是当前体系仍然需要保留的全局能力面。

2. `<worktree>/.vibe/`
   - 由 [lib/task_write.sh](lib/task_write.sh) 中 `_vibe_task_refresh_cache` 生成。
   - 由 [lib/task_actions.sh](lib/task_actions.sh) 在 `--bind-current` 路径触发。
   - 由 [lib/task_query.sh](lib/task_query.sh) 优先读取 `current-task.json` 作为当前任务指针。

这第二层最初的设计前提是：当前目录需要一个本地 task 指针和 focus/session 缓存，以支撑 flow/task 的快速恢复。但在当前边界模型下，这个前提已经不再成立：

- worktree 不再绑定 flow 语义本身。
- shell 不应通过本地缓存承担额外业务编排。
- 共享真源已经提供当前 worktree 与 task 的绑定关系。
- `task.md` 已被重新定义为 handoff，而不是 shell 查询真源。

## Problem Statement

保留 `<worktree>/.vibe/` 会制造三类漂移：

1. **真源漂移**
   - 当前任务既能从共享真源推导，又能从 `.vibe/current-task.json` 读取。
   - 一旦两者不一致，shell 需要决定信谁，边界开始恶化。

2. **语义漂移**
   - `.vibe/focus.md`、`.vibe/session.json` 与 `.agent/context/task.md` 都在描述“当前上下文”。
   - 这会让 save/continue 的语义重新散落成多文件模型。

3. **实现漂移**
   - 技能文档会继续把 `.vibe/*` 当作一等读取对象。
   - 测试会继续要求绑定 task 时生成 `.vibe/current-task.json`。
   - 文档会继续把本地缓存误描述为仍在使用的正式机制。

## Design Principles

### 1. 共享真源唯一化

当前 worktree 对应哪个 task，只允许由共享真源回答。

具体说：

- shell 通过当前 worktree 路径查询 `.git/vibe/worktrees.json`
- 再按 task id 读取 `.git/vibe/tasks/<task-id>/task.json` 或 registry 中的对应项

不再允许本地 `.vibe/current-task.json` 提供并列答案。

### 2. handoff 与真源分离

`.agent/context/task.md` 可以记录：

- 当前判断
- blockers
- 下一步建议
- 关键文件

但 shell 不能依赖它来回答“当前 task 是谁”这种确定性问题。否则只是把 `.vibe/current-task.json` 的冗余改写成另一个本地指针文件。

### 3. 删除冗余，不引入替身

本轮不是把 `.vibe/` 从一个文件名迁移到另一个文件名，而是直接取消这层本地缓存设计。

如果共享真源已经能回答问题，就不应再补一个本地副本。

## Options

### Option A: 保留本地 `.vibe/`，只把它降级成“可选缓存”

优点：

- 代码改动小。
- 可以继续兼容现有读取逻辑。

缺点：

- 冗余仍在。
- 技能和文档仍会持续围绕“是否读缓存”纠缠。
- 一旦缓存与共享真源不一致，shell 仍需处理冲突。

结论：不推荐。

### Option B: 删除本地 `.vibe/` 运行时语义，shell 只查共享真源

优点：

- 真源唯一。
- shell 查询逻辑更直接。
- save/continue/start 的职责边界更清楚。

缺点：

- 需要同步修改实现、测试、技能文档、结构文档。
- 需要明确区分 `<worktree>/.vibe/` 与 `~/.vibe/` 的不同命运。

结论：推荐。

### Option C: 用 `.agent/context/task.md` 取代 `.vibe/current-task.json`

优点：

- 人可读。
- 看起来“只剩一个本地文件”。

缺点：

- 仍然是本地指针层，没有消除冗余。
- shell 需要解析 Markdown 或依赖约定字段，本质上把业务判断重新塞回 shell。
- 会破坏 `task.md` 只是 handoff 的边界。

结论：拒绝。

## Recommendation

采用 Option B：删除 `<worktree>/.vibe/` 的运行时缓存语义，保留 `~/.vibe/` 的全局语义。

对应的系统收束方式：

- `vibe task update --bind-current` 只写共享真源，不再刷新本地 `.vibe/*`
- `vibe task list/show/...` 只按当前 worktree 路径从共享真源识别当前任务
- `/vibe-save (skill)` 只更新 `task.md` 并在必要时同步共享 task 最小事实
- `/vibe-continue (skill)` 先读共享真源，再读 `task.md`
- `/vibe-start` 只从 plan 与共享 task 元数据执行，不读 `.vibe/*`

## Proposed Runtime Semantics

### Current Task Resolution

当前任务解析顺序应收敛为：

1. 当前 worktree 绝对路径
2. `.git/vibe/worktrees.json` 中匹配 `worktree_path`
3. 得到 `current_task`
4. 去 `.git/vibe/tasks/<task-id>/task.json` 或 registry 读取任务事实

不再有 `.vibe/current-task.json` 分支。

### Save / Continue

`/vibe-save (skill)`：

- 保存 handoff 到 `.agent/context/task.md`
- 必要时调用 shell 同步最小 task 事实
- 不写 `.vibe/focus.md`、`.vibe/session.json`

`/vibe-continue (skill)`：

- 共享真源优先
- `task.md` 只补充解释信息
- 若无本地 handoff，不影响恢复当前 task 识别

## Implementation Surfaces

至少需要覆盖这些面：

1. Shell 实现
   - [lib/task_write.sh](lib/task_write.sh)
   - [lib/task_actions.sh](lib/task_actions.sh)
   - [lib/task_query.sh](lib/task_query.sh)

2. Skill / Workflow 文本
   - [skills/vibe-save/SKILL.md](skills/vibe-save/SKILL.md)
   - [skills/vibe-continue/SKILL.md](skills/vibe-continue/SKILL.md)
   - [.agent/workflows/vibe-start.md](.agent/workflows/vibe-start.md)

3. 结构与审计文档
   - [STRUCTURE.md](STRUCTURE.md)
   - [docs/tasks/2026-03-10-continue-save-start-audit/findings-2026-03-10.md](docs/tasks/2026-03-10-continue-save-start-audit/findings-2026-03-10.md)

4. 测试
   - [tests/test_task_ops.bats](tests/test_task_ops.bats)
   - 其他依赖 `.vibe/*` 行为的 task/flow 测试

## Risks

1. 某些 `flow` 视图可能间接依赖当前 task 指针读取逻辑，需要一起审查。
2. 历史文档和 archived plan 会继续出现 `.vibe/`，需要区分“历史记录”与“当前真源”。
3. 如果测试 fixture 直接断言 `.vibe/current-task.json` 存在，删除实现后会大面积失败，但这属于期望内回归修正。

## Success Criteria

满足以下条件才算完成：

1. 运行时实现不再创建 `<worktree>/.vibe/`。
2. 运行时实现不再读取 `<worktree>/.vibe/current-task.json`。
3. shell 只通过共享真源识别当前目录承载的 flow 所对应 task。
4. skill/workflow 文本不再把 `.vibe/*` 作为恢复入口。
5. 文档明确保留 `~/.vibe/`，并明确淘汰 `<worktree>/.vibe/`。