# Had-PR Flow Block/Resume Design

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 为 `vibe flow (shell)` 增加一个最小能力：当 flow 已进入 `open + had_pr` 且当前 PR 暂时无法继续推进时，允许显式标记为“阻塞/暂停”，随后在未来合法恢复并继续处理同一个 PR 的 follow-up。

**Non-Goals:** 不在本轮设计中重做 task/issue/workflow 编排；不把 skill 作为主要入口；不改变 `task.status` 的现有语义集合；不允许把已发 PR 的 flow 当作普通 `open + no_pr` flow 随意 `switch`。

**Architecture:** 当前系统把“现场层状态”与“执行层状态”分开。`worktrees.json.status` 只表达现场容器状态，不能直接承载 `blocked`；而 `git-workflow-standard` 已定义 `open + had_pr` 是合法的中间态，但当前 shell 只会阻止 resume，不支持显式 park/resume。因此新增能力应落在 `flow` 生命周期上，而不是偷用 worktree status。

**Tech Stack:** Zsh shell, `worktrees.json`, `flow-history.json`, `registry.json`, `gh`, Bats.

---

## 现状

1. `open + had_pr` 的 flow 当前只能继续留在原现场处理，或被 skill 解释为整合阶段。
2. `vibe flow switch` 对有 PR 历史的 flow 一律拒绝，见 `lib/flow_runtime.sh`。
3. `worktrees.json.status` 只允许 `active|idle|missing|stale`，不能新增 `blocked` 而不改标准。
4. task 层已有 `blocked`，但它表达的是执行单元阻塞，不等于“这个 had_pr flow 允许未来 resume”。

## 可选方案

### 方案 A：只放开 `flow switch`

做法：
- 修改 `flow switch`，允许重新进入 `had_pr` 的 flow。
- 不新增任何显式阻塞状态。

优点：
- 代码最少。
- 用户体验最直接。

缺点：
- 语义过宽。所有已发 PR 的 flow 都变成可随时重入，等于推翻现有 `open + had_pr` 边界。
- 失去“这是临时 park 过的 PR，还是普通 had_pr flow”的区分。
- 很容易把“继续当前 PR follow-up”和“随意回到旧 PR 做别的事”混在一起。

结论：
- 不推荐。

### 方案 B：把 `blocked` 挂到 task.status，switch 看 task

做法：
- 当用户显式 block 当前 had_pr flow 时，同时把关联 task 更新为 `blocked`。
- `flow switch` 在检测到 had_pr 时，如果对应 task.status=`blocked`，则允许 resume。

优点：
- 复用已有 `blocked` 枚举。
- 不新增新的共享状态字段。

缺点：
- task blocked 和 flow parked 不是同一语义。task blocked 可能是外部依赖、需求冻结、上游未合并，并不天然意味着“允许 later resume this PR via switch”。
- 当前很多 flow 并没有稳定绑定 task，像你这个现场就是 `current_task=null`。
- 会把 shell 能力绑死在 task 完整绑定上，导致 had_pr flow 的恢复能力不稳定。

结论：
- 可行但脆弱，不推荐作为主设计。

### 方案 C：新增 flow 级显式 parked/block 标记

做法：
- 在 flow 开放态记录里增加一个 flow 级字段，例如 `lifecycle_hint` 或 `delivery_state`。
- 合法枚举只覆盖 flow 生命周期补充语义，例如：
  - `active`
  - `blocked`
- 新增两个 shell 子命令：
  - `vibe flow block [--branch <ref>] [--reason <text>]`
  - `vibe flow resume <name>`
- `flow switch` 继续只允许 `open + no_pr`；
  `flow resume` 专门处理 `open + had_pr + blocked` 的恢复。

优点：
- 语义最干净，保留现有 `switch` 边界。
- “普通 had_pr”与“显式 park 过、允许恢复”的 flow 能清楚区分。
- 不依赖 task 是否绑定。

缺点：
- 需要给 flow 开放态补一个字段，并同步标准、帮助文档、测试。
- 比方案 A/B 多一点实现量。

结论：
- 推荐。

## 推荐设计

推荐采用方案 C，并坚持两个原则：

1. `switch` 不改语义  
   它仍只处理 `open + no_pr`。这样不会破坏既有标准，也不会把“旧 PR follow-up”误当成普通 flow 轮换。

2. 新增 `block/resume` 成对能力  
   `block` 只对 `open + had_pr` 生效，表示“当前 PR 暂停推进，但未来允许继续回到同一 PR 现场”。  
   `resume` 只对 `open + had_pr + blocked` 生效，表示“重新进入这个已 park 的 PR flow”。

## 语义建议

### 新字段位置

建议加在开放态 flow 记录中，也就是由 `worktrees.json` 经 `flow` 视图读取的结构上。

不要复用：
- `worktrees.json.status`
- `task.status`

建议新增：
- `flow_state` 或 `delivery_state`

推荐枚举：
- `active`
- `blocked`

解释：
- 这是 flow 层语义，不是现场容器健康状态。
- 它与 `worktrees.json.status=active|idle|missing|stale` 并存，不冲突。

### 新命令

1. `vibe flow block [--branch <ref>] [--reason <text>]`
   - 前提：目标 flow 必须已有 PR 事实
   - 行为：把 flow 标记为 `blocked`
   - 可选：记录 `blocked_reason`

2. `vibe flow resume <name>`
   - 前提：目标 flow 必须是 `open + had_pr + blocked`
   - 行为：切回目标 branch，并更新当前 worktree 对应的 flow 运行时
   - dirty worktree 处理：沿用当前 `switch` 的安全 stash/carry 逻辑

### 不变项

- `vibe flow switch` 仍拒绝进入 had_pr flow
- `vibe flow done` 仍只在 PR 已完成后关闭 flow
- `/vibe-integrate` 仍是默认上层编排；只是 shell 多了一个显式“暂停/恢复 PR flow”的原子能力

## 兼容性和风险

1. **标准冲突风险**
   - 需要更新 `git-workflow-standard.md`、`command-standard.md`、`data-model-standard.md`
   - 否则实现会先于标准漂移

2. **状态分裂风险**
   - 若同时维护 task blocked 和 flow blocked，必须明确二者不是同一字段、也不是自动同步

3. **视图兼容风险**
   - `flow show/status/list` 需要显示 `flow_state`
   - 否则用户看不到自己是否已 park 成功

4. **worktree 复用风险**
   - `resume` 若直接复用 `switch` 内核，要小心不要把 `resume` 误允许到 `open + no_pr`

## 最小实现面

建议新增/修改：
- `lib/flow_runtime.sh`
- `lib/flow_show.sh`
- `lib/flow_status.sh`
- `lib/flow_list.sh`
- `lib/flow_help.sh`
- `docs/standards/git-workflow-standard.md`
- `docs/standards/command-standard.md`
- `docs/standards/data-model-standard.md`
- `tests/flow/test_flow_lifecycle.bats`
- `tests/flow/test_flow_help_runtime.bats`

## 验证建议

Run:
```bash
bats tests/flow/test_flow_lifecycle.bats
```
Expected:
```text
新增 block/resume 生命周期用例通过
```

Run:
```bash
bats tests/flow/test_flow_help_runtime.bats
```
Expected:
```text
help/show/status/list 输出包含新的 flow block/resume 语义
```

## Recommendation

如果你要的是“只在 shell 放开，允许回来，并增加阻塞状态”，最合理的落点不是放宽 `switch`，而是：

- 保持 `switch` 原样
- 新增 `flow block`
- 新增 `flow resume`
- 给 flow 增加独立于 task/worktree 的 `flow_state=blocked`

这条路改动比“直接放开 switch”多一点，但语义是自洽的，不会把当前标准彻底打穿。

## Minimal-Command Variant

如果明确目标是“尽量不新增命令”，则可以进一步收敛成一个更小变体：

### 方案 D：`flow update` + `flow switch --force`

做法：
- 新增 `vibe flow update [<feature>|--branch <ref>] --state <active|blocked>`
- 在 `vibe flow switch <name>` 中新增 `--force`
- 但 `--force` 只允许放开一条规则：
  - 当目标 flow 已有 PR 历史时，只有它已经被显式标记为 `blocked`，才允许进入

优点：
- 只新增一个子命令，另一个是给现有命令补 flag
- `update` 语义和现有 `task update` 一致，符合“修改已有对象显式字段”的命令标准
- 用户入口更少，记忆负担低

缺点：
- `update` 作为泛化入口，help 和标准里必须非常清楚它只能改哪些 flow 字段，否则容易命令膨胀
- `--force` 这个名字过宽，默认会让人联想到“跳过全部检查”；实现必须严格限制，不能绕过 closed/missing/invalid branch 等检查

### 对 `--force` 的收口要求

如果采用这个变体，我建议把 `--force` 的真实语义写死为：

- 不跳过 branch 存在性检查
- 不跳过 closed flow 检查
- 不跳过 dirty worktree 的安全 carry 逻辑
- 不允许进入任意 had_pr flow
- 只允许进入 `open + had_pr + blocked` 的目标 flow

也就是说，这个 flag 的实际含义应是：

> “允许恢复一个已显式 blocked 的 had_pr flow”

而不是通用意义上的 force。

### 在两个推荐方案里的取舍

1. **语义最干净**：`flow block` + `flow resume`
   - 更直观
   - 最不容易误用

2. **命令最少**：`flow update --state blocked` + `flow switch --force`
   - 更符合你现在“不想新增太多命令”的目标
   - 但必须把 `--force` 收窄成“仅恢复 blocked had_pr flow”

### 修订后的推荐

如果你坚持减少命令面，我建议改成：

- 新增：`vibe flow update ... --state blocked`
- 修改：`vibe flow switch <name> --force`

并明确规定：

- `flow update` 目前只允许修改 `flow_state` 与可选 `blocked_reason`
- `switch --force` 只对 `open + had_pr + blocked` 生效
- 没有 `blocked` 标记的 had_pr flow，`switch` 仍拒绝

这样可以把新增命令数量压到最低，同时保住现有边界不被彻底打穿。
