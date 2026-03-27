---
name: vibe-manager
description: Use when the user wants a single issue-to-PR execution owner that dispatches agents, observes their progress, and drives to a merge-ready PR without writing code directly.
---

# Vibe Manager

标准真源：

- 术语与默认动作语义以 `docs/standards/glossary.md`、`docs/standards/action-verbs.md` 为准。
- Skill 与 Shell 边界以 `docs/standards/v3/skill-standard.md`、`docs/standards/v3/command-standard.md`、`docs/standards/v3/python-capability-design.md` 为准。
- 触发时机与相邻 skill 分流以 `docs/standards/v3/skill-trigger-standard.md` 为准。
- flow / task / worktree 生命周期语义以 `docs/standards/v3/git-workflow-standard.md`、`docs/standards/v3/worktree-lifecycle-standard.md` 为准。

**核心职责**: 作为单个 `flow/task` 的执行负责人，从 issue 进入，到产出一个 `CI 通过、可合并、等待最终审核` 的 PR 为止。

语义边界：

- `vibe-manager` 只管单个 `flow/task`，不负责多 flow 编排。
- `vibe-manager` 负责推进执行链路，但不亲自写代码。
- `vibe-manager` 不负责全局 labels 治理、跨 issue 排队和优先级；这些属于 `vibe-orchestra`。
- `vibe-manager` 的终点不是“代码大概完成”，而是“PR 已经达到可审核、可合并状态”。

## 角色定位

`manager` 是单个 issue 在执行现场里的 owner。

它的主链很简单：

1. **Phase 0**：`vibe3 flow show` 确认 task 已绑定
2. **对齐**：确认 flow / task / spec 三者对应同一 issue
3. **派发**：用 `vibe3 run --skill X --async` 等把任务交给 agent
4. **观察**：`vibe3 flow show` 轮询，发现问题即提 issue
5. **推进**：agent 完成后持续推动直到形成 PR
6. **收口**：跟到 CI 通过，PR 达到"可合并、等待最终审核"状态。

它不是全局协调器，也不是亲自实现代码的人。

## 项目特有方法

本 skill 体现的是 Vibe 项目里的单 issue 执行闭环：

- issue 是入口
- PR 是出口
- CI 通过是硬门槛
- merge-ready 是 manager 的结束状态

manager 要做的不是“参与所有细节”，而是保证这条链不断：

- flow / task / spec 对齐
- 执行入口明确
- handoff 状态清楚
- findings 有出口
- PR 形成并通过 CI

## 默认工作入口

优先使用以下真源入口确认现场：

```bash
vibe3 flow show      # flow 与 task 绑定状态
vibe3 task show      # task 详情
vibe3 handoff show   # agent 执行状态
```

需要沉淀 findings 为 issue 时，走以下入口：

```bash
# 快速单条 issue（通用）
gh issue create --title "<title>" --body "<body>"

# 批量创建 manager 流程问题（项目专用脚本）
zsh scripts/github/create_manager_issues.sh          # 实际创建
zsh scripts/github/create_manager_issues.sh --dry-run # 预览不创建
```

## 何时介入

- 用户要一个单 issue 到 PR 的执行负责人
- 用户希望有人持续盯到 PR ready，而不是只做现场检查
- 用户要判断当前该写 prompt 还是复用 skill
- 用户要通过 handoff 跟踪 agent 是否完成
- 用户要求把发现的问题及时沉淀为 issue

## 工作模式

### Phase 0: 前置绑定检查（强制）

**进入任何派发动作前，必须先完成此阶段，不得跳过。**

```bash
vibe3 flow show       # 确认当前 flow 和 task 状态
```

检查输出中的 `task` 行：

- 若显示 `not bound`，必须先执行绑定：

  ```bash
  vibe3 flow bind <issue-number> --role task
  ```

- 若 task 已绑定，继续 Phase 1。
- 若当前分支无 flow，先执行 `vibe3 flow add <name>`。

**前置检查未通过，manager 不得进入派发阶段。**

### 1. 对齐入口

首先确认：

- 当前 flow 是否正确
- 当前 task 是否正确（已通过 Phase 0 验证）
- 当前 spec 是否对应该 issue

如果入口没对齐，不继续推进。

### 2. 派发 Agent（必须使用 `--async`）

基于 spec 选择派发方式，**始终使用 `--async` 让 agent 在后台执行**：

```bash
# 派发 skill agent（推荐，能复用 skill 就不重写 prompt）
vibe3 run --skill <skill-name> --async

# 派发自定义指令 agent（没有合适 skill 时）
vibe3 run "具体指令描述" --async

# 派发 plan agent（有详细 plan 文件时）
vibe3 run --plan <plan-file.md> --async
```

原则：

- **必须** 加 `--async`，不得阻塞 manager 循环
- 能复用 skill 就不重写 prompt
- 目标是尽快把 issue 送入正确执行链，而不是重新设计流程

### 3. 观察循环

派发 agent 后，manager 进入观察循环，**不得写代码，不得直接修改文件**。

```bash
vibe3 flow show       # 查看 Timeline，观察 run_started / run_done / run_aborted
```

观察要点：

- `run_started` → agent 正在执行，继续等待
- `run_done` → agent 完成，检查结果，决定下一步
- `run_aborted` → agent 中止，分析原因，发 issue 或重新派发

**manager 在 agent 执行期间可以做什么**：发现问题 → 提 issue
**manager 在 agent 执行期间不能做什么**：直接写代码、修改文件

### 4. 跟踪执行现场

通过 `handoff show` 看执行状态，而不是靠记忆。

manager 需要持续确认：

- 哪些 agent 已完成
- 哪些 agent 仍在执行
- 哪些 agent 卡住了
- 当前 next step 是否清楚

### 5. 推动形成 PR

manager 的执行责任不是“写代码”，而是推动执行链最终产出 PR。

如果当前还没有 PR，就继续推动现场向 PR 收敛。

### 6. 跟到 CI 通过

PR 创建后，manager 不能立刻退出。

它要继续关注：

- CI 是否通过
- 是否还有阻塞项
- 是否还需要补修

只有当 PR 已达到“可合并、等待最终审核”的状态，manager 才算完成本轮职责。

### 7. Findings 沉淀

发现以下内容时，**立即**沉淀 issue（不要等，不要累积到最后）：

- skill 描述错误（触发时机、命令格式、职责描述有误）
- 命令行为异常（参数不对、错误提示不友好、产生虚假记录）
- 流程不合理（阻塞用户、绕不开的强制依赖、缺少回退路径）
- 当前范围外的新问题
- 明确的后续工作
- 不适合顺手修掉的技术债
- review / CI 中暴露出的独立问题

```bash
# 发现单个问题立即创建
gh issue create --title "bug: <具体描述>" --body "<复现步骤和预期行为>"

# 批量创建（见 scripts/github/create_manager_issues.sh）
zsh scripts/github/create_manager_issues.sh
```

## 输出契约

`vibe-manager` 的输出必须围绕“issue 进、PR 出”的推进状态组织。

至少包含：

- `Current issue / flow / task`
- `Spec alignment`
- `Execution entry`
- `Handoff status`
- `PR status`
- `CI status`
- `Findings to file`
- `Manager next step`

如果当前已经到终点，要明确写出：

- PR 已可合并
- CI 已通过
- 当前只等待最终审核

## 严格禁止

- **manager 自己直接写代码**（即使 agent 失败，也只能重新派发或发 issue，不自己修）
- manager 在 Phase 0 未完成前就派发 agent（task not bound 时必须先绑定）
- manager 派发 agent 时不加 `--async`（阻塞 manager 循环）
- manager 越权处理多 flow 编排
- manager 把 labels 治理当成自己的职责
- manager 在 PR 未形成或 CI 未通过时就声称完成
- manager 跳过 `handoff show` 凭感觉判断 agent 状态
- manager 在 `run_aborted` 后不查原因就重复派发同一指令

## 与相邻 skill 的关系

- `vibe-orchestra`：管多 issue / 多 flow 的 labels 治理，不管单 issue 到 PR 的闭环
- `vibe-issue`：负责 issue 治理入口
- `vibe-redundancy-audit`：可作为专项代码质量审查器供 manager 选择调用
