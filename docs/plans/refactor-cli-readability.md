# CLI Readability Refactor

**状态**: Ready
**Issue**: #392
**目标**: 基于 #390 之后的"读能力改造"——让命令更聚焦、更简洁、对 agent 更友好

---

## 背景

PR #390 完成了"写能力"的瘦身（删除 flow create/done）。
本次改造目标是"读能力"：统一 status 入口、简化命令接口、加强 PR 评论可见性，以及明确人机分工边界。

---

## Bug Fix（优先，属于 #390 的遗留）

### BF-1: `find_parent_branch` 返回 `origin` 而非真实父 branch

- **根本原因**：`git branch -a` 包含 remote tracking refs，`origin/HEAD` 短名恰好是 `origin`
- **修复**：`branch_utils.py` 中把 `git branch -a` 改为 `git branch -l`（只列 local branches）
- **文件**：`src/vibe3/utils/branch_utils.py` 第 41 行

### BF-2: `get_milestone_data` regression

- **根本原因**：简化后只返回 `{title, number, state}`，但 UI 还需要 `open`, `closed`, `issues`, `task_issue`
- **修复**：恢复 `FlowProjectionService.get_milestone_data()` 的完整实现（milestone issues 计数）
- **文件**：`src/vibe3/services/flow_projection_service.py`

---

## 功能改造

### F-1: `flow add` 语义调整（或更名 `flow update`）

**当前**：`flow add [NAME]` — 创建/注册 flow，支持 `--task`
**目标**：
- 位置参数改为 `BRANCH`（可选，默认当前 branch）
- 保留 `--name`、`--actor`（更新 flow 元数据，幂等）
- **移除 `--task`**（issue 绑定只走 `flow bind`）
- 考虑更名为 `flow update`（如果语义更清晰）

**文件**：`src/vibe3/commands/flow.py`（`add` 命令函数）

---

### F-2: `flow show` 显示 agent 签名

**当前**：显示 branch、parent、task、PR
**目标**：额外显示 actor 信息：
```
actor       latest: codex/gpt-4.1  plan: human  run: codex/gpt-4.1  review: human
```
- 数据来源：`FlowStatusResponse.latest_actor`、`planner_actor`、`executor_actor`、`reviewer_actor`（已在 SQLite）
- **文件**：`src/vibe3/ui/flow_ui.py`、`src/vibe3/ui/flow_ui_timeline.py`

---

### F-3: 移除 `flow list`

- 不重要，`flow status` 已覆盖
- **文件**：`src/vibe3/commands/flow.py`（删除 `list_flows` 命令注册）

---

### F-4: 新增 `vibe3 status`，移除 `vibe3 task`、`vibe3 orchestra status`

**目标**：统一入口，一条命令看全局

```
$ vibe3 status
Active Flows:
  task/issue-42  state/in-progress  PR #390  worktree: wt-claude-v3  actor: codex/gpt-4.1
  task/issue-55  state/ready        (no PR)   worktree: wt-main

Orchestra:
  Server: running  Issues: 3 ready  Circuit breaker: off
```

**实现思路**：
- 新建 `src/vibe3/commands/status.py`（调用 FlowService + OrchestraConfig）
- 移除 `vibe3 task`（`task list` 功能合并到 `flow status`）
- 移除 `vibe3 orchestra status`（合并到 `vibe3 status`）
- **文件**：`src/vibe3/commands/status.py`（新建）、`src/vibe3/cli.py`（注册）

---

### F-5: `vibe3 pr show` 增加评论显示

**当前**：显示 PR diff、改动分析
**目标**：额外显示 PR 评论（review comments + general comments）
- `gh pr view --comments` 只能看 general comments，不含 review line comments
- 需要额外调用 `gh api repos/{owner}/{repo}/pulls/{pr}/comments` 获取 review comments
- **文件**：`src/vibe3/commands/pr.py`、`src/vibe3/clients/github_client.py`

---

### F-6: `vibe3 pr create` 改为 human-only draft 入口

**当前**：`vibe3 pr create` — 直接创建 PR
**目标**：
- 永远创建 draft PR
- 显示警告：
  ```
  [yellow]此命令仅建议人类使用。Agent 请直接使用 gh pr create --draft 命令。[/]
  [yellow]如需继续，请使用 --yes 确认。[/]
  ```
- 未传 `--yes` 时直接退出（`raise typer.Exit(0)`）
- 考虑更名为 `vibe3 pr draft --yes`

**文件**：`src/vibe3/commands/pr.py`（`create` 命令）

---

### F-7: `vibe3 check` 简化

**当前**：`check --fix --all` 三个独立 flag 组合
**目标**：
- 移除 `--all` 和 `--fix` 参数
- `vibe3 check` = 原来的 `check --fix --all`（检查所有 active flows，自动修复）
- 保留 `--init`（回填远端 index，场景不同）

**额外逻辑**：
- 检查时发现本地已不存在的 branch（`git branch -l` 不包含）→ 标记 flow status 为 `aborted`
- 现有 `_mark_flow_done()` 同级，新增 `_mark_flow_aborted_if_branch_deleted()`

**文件**：`src/vibe3/commands/check.py`、`src/vibe3/services/check_service.py`、`src/vibe3/services/check_execute_mixin.py`

---

## 改动范围统计

| 任务 | 主要文件 | 类型 | 规模 |
|------|----------|------|------|
| BF-1 | branch_utils.py | 1-line fix | 极小 |
| BF-2 | flow_projection_service.py | 恢复删除代码 | 小 |
| F-1 | commands/flow.py | 改接口 | 小 |
| F-2 | ui/flow_ui*.py | 新增展示 | 小 |
| F-3 | commands/flow.py | 删一行 | 极小 |
| F-4 | commands/status.py（新）+ cli.py | 新增 + 删除 | 中 |
| F-5 | commands/pr.py + github_client.py | 新增 API 调用 | 小 |
| F-6 | commands/pr.py | 改逻辑 | 极小 |
| F-7 | check.py + check_service.py | 改接口 + 新增逻辑 | 小 |

**净增代码**：约 +100 行 / -80 行

---

## 实施顺序

每步独立 commit，失败可单步 revert：

1. **BF-1** — `find_parent_branch` 只用 local branches
2. **BF-2** — 恢复 `get_milestone_data` 完整实现
3. **F-3** — 删除 `flow list`（最小改动，验证回归）
4. **F-1** — `flow add` → `flow update` 语义调整
5. **F-2** — `flow show` 显示 actor
6. **F-7** — `vibe3 check` 简化（含 aborted 逻辑）
7. **F-4** — 新增 `vibe3 status`，移除 `task`/`orchestra status`
8. **F-5** — `vibe3 pr show` 评论
9. **F-6** — `vibe3 pr create` human-only gate

---

## 验证清单

- [ ] `flow show` 显示 `parent: main`（而非 `parent: origin`）
- [ ] `flow show` 显示 actor 签名
- [ ] `flow update --name foo --actor codex` 更新元数据，不影响 issue 绑定
- [ ] `vibe3 check`（无参数）自动 fix all active flows，删除分支标为 aborted
- [ ] `vibe3 status` 显示 flows + orchestra 状态
- [ ] `vibe3 pr show 390` 显示评论
- [ ] `vibe3 pr draft`（无 --yes）显示警告并退出
- [ ] `vibe3 pr draft --yes` 正常创建 draft PR
- [ ] `vibe3 task` 命令不存在（或 deprecation warning）
- [ ] `vibe3 orchestra status` 不存在（合并进 `vibe3 status`）
