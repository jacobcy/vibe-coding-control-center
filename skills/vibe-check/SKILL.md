---
name: vibe-check
description: Use when the user wants to inspect the current runtime scene with vibe3 task status or vibe3 flow status, verify whether flow/task state is synchronized with vibe3 check, reset other auto-task worktrees with vibe3 task resume, or mentions "/vibe-check" or "check runtime". Do not use for roadmap prioritization or roadmap-task mapping.
---

# /vibe-check (/check) - task-flow 审计驱动修复

现场观察与修复分三类命令：

- `uv run python src/vibe3/cli.py task status` / `--all`：看 orchestra 与 task 现场
- `uv run python src/vibe3/cli.py flow status` / `flow show`：看当前或全局 flow 现场
- `uv run python src/vibe3/cli.py check`：只检查 flow 与 task 是否同步
- `uv run python src/vibe3/cli.py task resume ...`：把其他 auto task flow 的 worktree / runtime 现场回退到可恢复状态

`vibe-check` skill 负责：

1. 读取审计输出
2. 做业务判断
3. 只修复 `task <-> flow` / runtime 绑定与 auto-task scene recovery 问题
4. 只通过 Shell API 执行安全修复

`vibe-check` 是 runtime / recovery audit，不承担 task-centered audit。

对象约束：

- 任何修复都必须先读 shell 审计输出，再决定动作

**Announce at start:** "我正在使用 vibe-check 技能读取 runtime 现场与审计结果，并在可确定时通过 Shell API 修复共享状态问题。"

> 项目命令参考见 `skills/vibe-instruction/SKILL.md`

## 真源边界

共享真源与本地事实边界以 `docs/standards/v3/command-standard.md` 为准；skill 只读取 shell 暴露的 flow / task / handoff 审计结果，不直接读取底层 JSON / SQLite。

禁止：

- skill 直接编辑 `.git/vibe/*.json`
- 把 `.agent/context/task.md` 当作共享真源
- 把 `uv run python src/vibe3/cli.py check` 扩展成默认自动修复器

## 执行流程

### Step 1: 先读现场

优先运行：

```bash
uv run python src/vibe3/cli.py task status --all
uv run python src/vibe3/cli.py flow status
```

如果是当前分支现场，再补：

```bash
uv run python src/vibe3/cli.py flow show
```

这一层回答的是：

- 当前有哪些 active / ready / blocked issues
- 当前分支是不是已注册 flow
- auto task scene 和 manual scene 是否异常

### Step 2: 再做同步审计

当且仅当需要确认 flow 与 task 是否同步时，再运行：

```bash
uv run python src/vibe3/cli.py check
```

`check` 的职责是审计同步性，不是默认的“看现场”入口，也不是默认自动修复器。

## 职责边界

`vibe-check` 只处理：

- task runtime 指向不存在的 worktree
- 已完成 / 已归档 task 仍残留 runtime 绑定
- 当前现场绑定与 task runtime 的确定性修复
- 需要把其他 auto-created task/issue-\* 现场回退到 ready / blocked recovery 起点
- 基于 shell 输出可直接确认的 flow/task 状态缺失提示

`vibe-check` 不处理：

- `task <-> issue` 对应关系修复
- task 未链接 issue 的规划问题
- task 应该归属于哪个 issue 的语义判断
- GitHub Issue intake、模板补全、查重与创建

flow/task 绑定的 task issue 只能作为审计证据或转交依据，不得在 skill 内重写成 GitHub 官方身份。

前三项属于 `vibe-task` 的审计/修复范围。

其中：

- Issue intake 与 GitHub 创建属于 `vibe-issue`
- 此 skill 中的 `worktree` 只表示物理目录容器，不表示 runtime 主体；runtime 主语仍是 `task <-> flow` / branch 绑定

## Step 3: 分类问题

把问题分成三类：

### A. 可确定自动修复

满足以下条件才可自动修复：

- shell 已提供原子命令
- 修复目标唯一
- 不需要语义猜测

当前允许的确定性修复：

- `completed/archived task still has runtime binding: <task-id>`
  - 修复命令：仅限当前 `vibe3 check` 默认模式已经明确支持的最小修复
- 当前目录承载的 flow 就是目标 task 的确定性现场
  - 修复命令：仅限当前 `vibe3 check` 默认模式已经明确支持的最小修复
- 其他 auto task flow 需要回退 worktree / runtime 现场
  - 修复命令：`uv run python src/vibe3/cli.py task resume --failed|--blocked|--all ...`

### B. 需要用户确认

以下情况不允许直接修：

- `runtime points to missing worktree: <task-id>:<worktree-name>`
  - shell 能发现缺口，但无法仅凭审计结果判断应解绑还是重绑
- 要不要回退其他 issue 的 auto task scene
  - shell 有 `task resume` 能力，但需要用户确认影响范围（单 issue / failed / blocked / all）
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

## Step 4: 执行修复

对 A 类问题，只调用当前真实存在的 shell 命令，不做 JSON / SQLite 直写：

```bash
uv run python src/vibe3/cli.py check
uv run python src/vibe3/cli.py task resume --failed --yes
uv run python src/vibe3/cli.py task resume --blocked --yes
uv run python src/vibe3/cli.py task resume --all --yes
```

如果命令失败：

- 立即停止该条修复
- 记录失败命令和错误
- 不继续假设状态已同步

## Step 5: 重新验证

修复后必须重新运行：

```bash
uv run python src/vibe3/cli.py task status --all
uv run python src/vibe3/cli.py flow status
uv run python src/vibe3/cli.py check
```

## Step 6: 报告

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
  command: uv run python src/vibe3/cli.py check

需要确认：
- runtime points to missing worktree: 2026-03-08-bar:wt-old
  reason: shell 无法仅凭审计结果判断应解绑还是重绑

验证结果：
- uv run python src/vibe3/cli.py check  -> clean
```

## 与其他命令的关系

- `uv run python src/vibe3/cli.py task status --all`：主现场看板，优先用于看 orchestra / task runtime
- `uv run python src/vibe3/cli.py flow status` / `flow show`：flow 现场读取
- `uv run python src/vibe3/cli.py check`：只负责检查 flow 和 task 是否同步
- `uv run python src/vibe3/cli.py task resume`：把其他 auto-task flow 的 worktree / runtime 现场回退
- `/vibe-check`：基于上述命令解释 runtime 审计结果并编排最小修复
- `/vibe-task`：处理 task 与元数据审计修复
