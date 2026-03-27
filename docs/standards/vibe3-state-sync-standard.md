# Vibe3 状态确认与联动标准

**维护者**: Vibe Team  
**最后更新**: 2026-03-27  
**状态**: Active

---

## 1. 目标

统一 `flow/branch`、`task/issue`、`pr` 三者的联动规则，明确命令执行范式：

1. 先确认现场事实（GitHub/Git）。
2. 若事实已成立，只做最小确认动作并回写本地状态。
3. 若事实未成立，但满足条件，则执行最小推进动作并回写本地状态。
4. 若事实未成立且不满足条件，则阻断；仅在允许时可通过 `--yes` 绕过。

---

## 2. 总原则

### 2.1 真源优先

- GitHub PR/Issue、Git branch 状态是外部事实真源。
- SQLite 是本地执行缓存，不得覆盖真源事实。

### 2.2 幂等优先

- 命令必须可重复执行。
- 已达到目标状态时，不重复副作用，只做确认与同步。

### 2.3 最小纠正

- 仅纠正与当前命令目标直接相关的状态。
- 不在同一命令内偷偷扩展其它状态变更。

### 2.4 显式绑定

- `flow bind` 必须显式输入 issue；不得隐式猜测 task。
- 多 task 绑定允许追加（同一 flow 可有多个 `role=task`）。

---

## 3. 状态判定表（命令级）

| 命令 | 先检查事实 | 已是目标状态 | 可推进条件 | 不满足条件 | `--yes` 策略 |
|---|---|---|---|---|---|
| `vibe3 pr create` | 当前 branch 是否已有 PR | 返回现有 PR 并同步本地 `pr_number` / 状态 | 无 PR 时创建 PR，并写入 `state/in-progress` | 分支不合法/创建失败则阻断 | 不允许绕过“无效分支/创建失败” |
| `vibe3 pr ready` | PR 是否已 ready | 只确认 ready，并同步本地 ready 状态 | PR 为 draft 时执行 ready | PR 不存在/不可 ready 则阻断 | 仅允许绕过质量门禁，不绕过真源事实 |
| `vibe3 flow done` | PR 是否 merge；task 是否存在 | 已 merge 时直接执行 closeout（分支/flow/task） | 未 merge但可 merge时先 merge，再 closeout | PR 不可 merge、关键前置缺失则阻断 | 仅允许绕过业务门禁；不绕过“真源不可达/merge 失败” |
| `vibe3 flow create` | 当前 worktree flow 状态是否允许开新目标 | 若目标 branch+flow 已存在，则确认存在并同步 | 允许创建时：创建 branch + 注册 flow + 可选绑定 task/spec | 当前 flow 活跃且未到可放行状态则阻断 | 不允许绕过 worktree 隔离规则 |
| `vibe3 flow add` | 当前 branch 是否已有 flow | 已有则确认存在并同步（不重复注册） | 无 flow 时注册当前 branch 为 flow | branch 非法或注册失败阻断 | 不允许绕过真源冲突 |
| `vibe3 flow bind` | 目标 issue 是否存在；当前 flow 是否存在 | 已绑定同角色则确认，不重复写入 | 未绑定则追加绑定（支持多 task） | issue 无效/flow 不存在则阻断 | 不允许绕过显式绑定输入 |

---

## 4. 联动关系（Flow / Task / PR）

### 4.1 PR 生命周期到 Flow/Task

1. `pr create`
   - 目标状态：`state/in-progress`
   - 联动：更新 flow 的 PR 关联状态；task 进入 `state/in-progress`（或等价执行中状态）

2. `pr ready`
   - 目标状态：`state/merge-ready`
   - 联动：flow 与关联 task 同步为 `state/merge-ready`（或等价待合并状态）

3. `flow done`
   - 目标状态：flow 关闭
   - 联动：
     - 若 PR 未 merge 且可 merge：先 merge。
     - closeout flow branch。
     - 关闭当前 flow 下所有 `role=task` 的 issue（不影响 `related/dependency`）。

### 4.2 Flow 与 Task 绑定

- `flow bind --role task` 允许多条 `task` 关系并存。
- `flow done` 针对该 flow 的全部 `task` 关系执行关闭联动。
- `related` / `dependency` 仅参与关联与阻塞语义，不参与 done 自动关闭。

---

## 5. `--yes` 绕过边界

### 5.1 可绕过

- 交互确认提示（confirm）。
- 业务门禁（如质量门禁、覆盖率门禁）中的“软阻断”。

### 5.2 不可绕过

- 真源事实冲突（PR/Issue 不存在、branch 不存在、merge 失败）。
- worktree 隔离硬规则。
- 缺少显式输入（如 `flow bind` 的 issue）。

---

## 6. 落地要求

1. 查询类命令不得降级已确认状态（避免“读操作把状态打回去”）。
2. 所有状态回写必须基于“真源检查结果”，不基于猜测。
3. 命令输出需明确属于哪类结果：
   - `confirmed`：事实已满足，仅确认同步。
   - `advanced`：执行了最小推进动作。
   - `blocked`：不满足条件且不可绕过。

---

## 7. 与现有标准关系

- 本文档定义状态联动与判定表真源。
- 命令参数与命令面定义以 [vibe3-command-standard.md](vibe3-command-standard.md) 为准。
- issue 角色语义以 [issue-standard.md](issue-standard.md) 为准。
- 标签定义与集合以 [github-labels-standard.md](github-labels-standard.md) 为准。

---

## 8. 标签联动映射（与标签标准一致）

本节定义 `vibe3` 命令与标签状态机的标准映射，用于保证“状态确认优先 + 幂等回写”。

### 8.1 编排状态标签（`state/*`）

| 命令 | 目标状态标签 | 规则 |
|------|-------------|------|
| `vibe3 plan ...` | `state/claimed` | 先读当前状态；若已是 `state/claimed` 仅确认，不重复迁移 |
| `vibe3 run ...` | `state/in-progress` | 先读当前状态；若已是 `state/in-progress` 仅确认 |
| `vibe3 review ...` | `state/review` | 先读当前状态；若已是 `state/review` 仅确认 |
| `vibe3 flow blocked ...` | `state/blocked` | 阻塞成立后迁移；若已是 `state/blocked` 仅确认 |
| `vibe3 pr ready ...` | `state/merge-ready` | PR ready 成立后迁移；若已是 `state/merge-ready` 仅确认 |
| `vibe3 flow done ...` | `state/done` | flow closeout 成功后迁移；若已是 `state/done` 仅确认 |

约束：
- 迁移动作必须通过 `LabelService` 保证 `state/*` 单值。
- 查询类命令（`show/status/list`）不得写入或降级 `state/*`。

### 8.2 关系镜像标签（`vibe-task`）

| 关系真源（`issue_role`） | `vibe-task` 镜像动作 |
|--------------------------|---------------------|
| `task` | 确保存在（幂等 add） |
| `dependency` | 确保存在（幂等 add） |
| `related` | 不存在则跳过；若存在则应支持幂等移除 |

约束：
- 镜像失败不影响 `issue_role` 真源。
- `vibe-task` 不能用于反推 `issue_role`。

### 8.3 幂等确认原则

对于以上所有命令，统一遵循：

1. 先确认远端事实（当前 label 状态）。
2. 若目标状态已成立：返回 `confirmed`，只做必要本地同步。
3. 若目标状态未成立且可迁移：执行最小迁移，返回 `advanced`。
4. 若目标状态未成立且不可迁移：返回 `blocked`，不得隐式强制跳转。
