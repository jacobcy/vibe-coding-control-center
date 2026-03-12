---
name: vibe-check
description: Use when the user wants to inspect or repair task-flow/worktree runtime consistency after shell audit, asks whether a task binding or current worktree state is stale, or mentions "/vibe-check" or "check runtime". Do not use for roadmap prioritization or roadmap-task mapping.
---

# /vibe-check (/check) - task-flow 审计驱动修复

`vibe check(shell)` 只负责审计。`vibe-check` skill 负责：

1. 读取审计输出
2. 做业务判断
3. 只修复 `task <-> flow` / runtime 绑定问题
4. 只通过 Shell API 执行安全修复

`vibe-check` 是 runtime / recovery audit，不承担 task-centered audit。

对象约束：

- `roadmap item = GitHub Project item mirror`
- `task = execution record`
- `spec_standard/spec_ref` 是 task 的 execution spec 扩展字段
- 任何修复都必须先读 shell 审计输出，再决定动作

**Announce at start:** "我正在使用 vibe-check 技能读取 shell 审计结果，并在可确定时通过 Shell API 修复共享状态问题。"

标准真源：

- 术语与默认动作语义以 `docs/standards/glossary.md`、`docs/standards/action-verbs.md` 为准。
- Skill 与 Shell 边界以 `docs/standards/skill-standard.md`、`docs/standards/command-standard.md`、`docs/standards/shell-capability-design.md` 为准。
- 触发时机与相邻 skill 分流以 `docs/standards/skill-trigger-standard.md` 为准。
- task / flow / worktree 生命周期语义以 `docs/standards/git-workflow-standard.md`、`docs/standards/worktree-lifecycle-standard.md` 为准。

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

若要核对 execution spec 证据，可额外读取 `vibe task list --json` 或 `vibe task show <task-id> --json` 的 `spec_standard/spec_ref` 字段。

## 职责边界

`vibe-check` 只处理：

- task runtime 指向不存在的 worktree
- 已完成 / 已归档 task 仍残留 runtime 绑定
- 当前现场绑定与 task runtime 的确定性修复
- 基于 shell 输出可直接确认的 execution spec 缺失提示

`vibe-check` 不处理：

- `roadmap item <-> task` 对应关系修复
- roadmap item 未链接 task 的规划问题
- task 应该归属于哪个 roadmap item 的语义判断
- GitHub Issue intake、模板补全、查重与创建

`execution_record_id` 与 `spec_standard/spec_ref` 只能作为审计证据或转交依据，不得在 skill 内重写成 GitHub 官方身份。

前三项属于 `vibe-task` 的审计/修复范围。

其中：

- roadmap 规划与版本归类属于 `vibe-roadmap`
- Issue intake 与 GitHub 创建属于 `vibe-issue`

## Step 2: 分类问题

把问题分成三类：

### A. 可确定自动修复

满足以下条件才可自动修复：

- shell 已提供原子命令
- 修复目标唯一
- 不需要语义猜测

当前允许的确定性修复：

- `completed/archived task still has runtime binding: <task-id>`
  - 修复命令：`vibe task update <task-id> --unassign`
- 当前目录承载的 flow 就是目标 task 的确定性现场
  - 修复命令：`vibe task update <task-id> --bind-current`

### B. 需要用户确认

以下情况不允许直接修：

- `runtime points to missing worktree: <task-id>:<worktree-name>`
  - shell 能发现缺口，但无法仅凭审计结果判断应解绑还是重绑
- 需要从 PR / 评论 / 文档语义推断 task 完成度
- 需要在多个 worktree / task 之间做语义匹配

此时必须向用户展示：

- 审计证据
- 可选修复命令
- 不确定点

### C. shell 能发现但不能修

如果发现问题但缺少原子能力，例如：

- 现场记录需要删除或改成 `missing/stale`，但 shell 没有单独的 flow 修复 API
- 需要跨多个 worktree 做事务修复，但 shell 只有单 task 写入口

则必须停止并明确报告 shell 能力缺口。

## Step 3: 执行修复

对 A 类问题，逐条调用 shell 命令，不做 JSON 直写：

```bash
vibe task update "$task_id" --unassign
vibe task update "$task_id" --bind-current
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
- completed/archived task still has runtime binding: 2026-03-08-foo
  command: vibe task update 2026-03-08-foo --unassign

需要确认：
- runtime points to missing worktree: 2026-03-08-bar:wt-old
  reason: shell 无法仅凭审计结果判断应解绑还是重绑

验证结果：
- vibe check link --json -> clean
```

## 与其他命令的关系

- `vibe check`：审计
- `vibe task update`：原子写入
- `/vibe-check`：解释 task-flow 审计并编排修复
- `/vibe-task`：处理 roadmap-task 与 registry 审计修复
