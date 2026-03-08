---
name: vibe-check
description: Use when the user wants to verify project shared-state consistency and, when safe, repair deterministic gaps through Shell APIs. This skill consumes audit output; it does not edit shared JSON directly.
---

# /check - 审计驱动修复

`vibe check(shell)` 只负责审计。`vibe-check` skill 负责：

1. 读取审计输出
2. 做业务判断
3. 只通过 Shell API 执行安全修复

**Announce at start:** "我正在使用 vibe-check 技能读取 shell 审计结果，并在可确定时通过 Shell API 修复共享状态问题。"

## 真源边界

共享真源固定为：

- `$(git rev-parse --git-common-dir)/vibe/roadmap.json`
- `$(git rev-parse --git-common-dir)/vibe/registry.json`
- `$(git rev-parse --git-common-dir)/vibe/worktrees.json`

禁止：

- skill 直接编辑 `.git/vibe/*.json`
- 把 `.agent/context/task.md` 当作共享真源
- 把 `vibe check(shell)` 扩展成默认自动修复器

## 执行流程

### Step 1: 运行 shell 审计

先运行：

```bash
vibe check --json
```

必要时补充定向检查：

```bash
vibe check link --json
vibe roadmap audit --check-links --json
```

## Step 2: 分类问题

把问题分成三类：

### A. 可确定自动修复

满足以下条件才可自动修复：

- shell 已提供原子命令
- 修复目标唯一
- 不需要语义猜测

当前允许的确定性修复：

- `roadmap item missing task back-link: <roadmap-item-id>:<task-id>`
  - 修复命令：`vibe task update <task-id> --roadmap-item <roadmap-item-id>`
- `task missing roadmap back-link: <task-id>:<roadmap-item-id>`
  - 修复命令：`vibe task update <task-id> --roadmap-item <roadmap-item-id>`
- `completed/archived task still has runtime binding: <task-id>`
  - 修复命令：`vibe task update <task-id> --unassign`

### B. 需要用户确认

以下情况不允许直接修：

- `unlinked roadmap item: <roadmap-item-id>`
  - shell 只能确认“未链接”，不能判断“应该链接到哪个 task”
- 需要从 PR / 评论 / 文档语义推断 task 完成度
- 需要在多个 task / roadmap item 之间做语义匹配

此时必须向用户展示：

- 审计证据
- 可选修复命令
- 不确定点

### C. shell 能发现但不能修

如果发现问题但缺少原子能力，例如：

- dangling ref 需要移除，而 shell 没有 remove/unlink API
- 需要跨多个文件做事务修复但只有单侧写接口

则必须停止并明确报告 shell 能力缺口。

## Step 3: 执行修复

对 A 类问题，逐条调用 shell 命令，不做 JSON 直写：

```bash
vibe task update "$task_id" --roadmap-item "$roadmap_item_id"
vibe task update "$task_id" --unassign
```

如果命令失败：

- 立即停止该条修复
- 记录失败命令和错误
- 不继续假设状态已同步

## Step 4: 重新验证

修复后必须重新运行：

```bash
vibe check --json
```

若修的是链接问题，额外运行：

```bash
vibe check link --json
```

## Step 5: 报告

最终报告固定包含：

- 审计结论
- 已执行的 shell 命令
- 修复成功项
- 需用户确认项
- shell 能力缺口

输出示例：

```text
📋 Vibe Check Report

已自动修复：
- task missing roadmap back-link: 2026-03-08-foo:rm-1
  command: vibe task update 2026-03-08-foo --roadmap-item rm-1

需要确认：
- unlinked roadmap item: gh-52
  reason: shell 无法判断应链接到哪个 task

验证结果：
- vibe check link --json -> clean
```

## 与其他命令的关系

- `vibe check`：审计
- `vibe task update`：原子写入
- `vibe roadmap audit`：补充规划层检查
- `/vibe-check`：解释审计并编排修复
