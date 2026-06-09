---
name: vibe-continue
description: Use when the user wants to resume work on an existing branch or flow. Reads context, executes the next step, reviews the result, and reports to the user before proceeding. Equivalent to superpowers:executing-plans, using vibe3 as the execution backend.
---

# /vibe-continue

恢复已有 flow 并逐步执行。每步完成后审查结果，发现问题直接修正，修正后再进入下一步。

## 核心原则

**执行 → 审查 → 修正 → 报告 → 下一步**

不是"报告问题然后继续跑"。审查是修正门禁，不是信息展示。

**修正优先级**：
1. **明确问题**（测试失败、逻辑错误、参数错误）→ 直接修正，不问用户
2. **模糊问题**（范围疑问、设计决策、性能取舍）→ 向用户报告，等决策
3. **无问题** → 报告结果，进入下一步

## Step 1: 恢复上下文

并行执行：

```bash
vibe3 flow show [--branch <b>]
vibe3 handoff show @current [--branch <b>]
git status
```

检查并清理残留 Monitor：
```bash
TaskList  # 查看活跃 Monitor
# 任何残留 Monitor → TaskStop 清理
```

提取当前状态，决定下一步。

## Step 2: 执行下一步

根据 flow 状态决定：

```
plan_ref 为空  → vibe3 plan
run_ref 为空   → vibe3 run
review_ref 为空 → vibe3 review
PR 未创建      → vibe3 run --publish
```

命令启动后，用 Monitor 监控完成信号（不要轮询等待）。

### 失速接管（Rate Limit / 卡死）

如果 vibe3 run 的 agent 遇到持续问题（rate limit、卡死、反复重试），**不要无限等待**，直接接管：

**接管触发条件**：
- agent 日志中出现连续 `api_retry` 且 `error_status=429` 超过 3 次
- Monitor 超时（20 分钟内未完成）
- tmux session 存活但 agent 无新输出超过 5 分钟

**接管流程**：
1. 停止 tmux session：`tmux kill-session -t vibe3-executor-issue-<id>`
2. 清理 Monitor：TaskStop
3. 读取 agent 已完成的部分：检查 worktree 中的代码变更（`git diff`）
4. **直接在当前 session 继续实现**：按 plan 的剩余步骤执行
5. 完成后手动记录 `vibe3 handoff append`

**原则**：vibe3 run 是便利工具，不是必须依赖。主 agent 有能力直接实现。

### Monitor 生命周期管理

每个 Monitor 只服务一个命令。完成后**立即清理**：

```
启动命令 → 创建 Monitor → 等待事件
  ↓
Monitor 触发（命令完成/失败/超时）
  ↓
立即 TaskStop 清理该 Monitor
  ↓
进入审查流程
```

**每次进入 Step 2 前**，先检查并清理上一步的 Monitor：
1. 用 TaskList 查看活跃 Monitor
2. 如果上一步的 Monitor 仍在运行（应已触发）→ TaskStop 清理
3. 然后启动新命令的 Monitor

**ScheduleWakeup 同理**：每次循环只保留一个 ScheduleWakeup。新循环开始时，上一个 ScheduleWakeup 应已被唤醒（或超时），不需要手动清理。

**禁止**：
- ❌ 同时运行多个 Monitor 监听同一命令
- ❌ Monitor 触发后不清理让它继续运行
- ❌ 让已超时的 Monitor 残留

**示例**：
```bash
# Step 2: plan 完成后
Monitor triggered → TaskStop(monitor_id)  # 清理 plan monitor
# 进入 Step 3 审查

# Step 2: 启动 run
New Monitor created for run
ScheduleWakeup set as fallback
```

## Step 3: 审查 + 修正（关键）

每步完成后，**必须**审查并修正发现的问题。

### 审查 → 修正流程

```
读取 artifact
  ↓
逐项审查（范围、质量、测试、一致性）
  ↓
发现问题？
  ├─ 明确问题 → 直接修正 → 重新验证 → 报告修正内容
  ├─ 模糊问题 → 向用户报告 → 等待决策
  └─ 无问题   → 报告结果
  ↓
进入下一步
```

### vibe3 plan 完成后

读取 `vibe3 handoff show @plan`，审查：

1. **范围**：是否覆盖 issue 所有需求？遗漏 → **在 plan 文件中补充**
2. **可行性**：步骤是否可执行？假设不成立 → **修正 plan 步骤**
3. **逻辑错误**：参数错误、接口不匹配、逻辑矛盾 → **直接修正 plan**
4. **测试覆盖**：有测试步骤吗？缺失 → **补充测试步骤**

修正 plan 后报告：
```
Plan 审查：
- 范围：完整 / 已补充 XX
- 修正：修正了 XX 问题（具体说明）
- 风险：低 / 中 / 高
- 状态：通过 → 继续 run
```

### vibe3 run 完成后

读取 `vibe3 handoff show @report` + 检查代码，审查：

1. **测试**：跑失败的测试 → **直接修复代码直到测试通过**
2. **逻辑错误**：实现与 plan 不符 → **修正代码**
3. **代码质量**：明显 bug、类型错误 → **直接修复**
4. **Plan 一致性**：偏离 plan 且无合理理由 → **修正为 plan 描述的方式**

修正代码后报告：
```
Run 审查：
- 变更：N 个文件，+X/-Y 行
- 修正：修复了 XX（测试失败/逻辑错误/...）
- 测试：全部通过
- Plan 一致性：一致 / 有偏离（原因）
- 状态：通过 → 继续 review
```

### vibe3 review 完成后

读取 `vibe3 handoff show @audit`，审查：

1. **阻塞项**（CRITICAL/HIGH）→ **直接修复代码，重新跑 review**
2. **建议项**（MEDIUM/LOW）→ 评估后决定是否修复
3. **误报** → 记录但不修改
4. **修复后** → 重新跑 `vibe3 review` 确认通过

修正后报告：
```
Review 审查：
- Verdict: PASS / 修正后 PASS / CONDITIONAL
- 修正：修复了 N 个阻塞项（列出）
- 遗留：M 个建议项（不阻塞）
- 状态：通过 → 继续 publish
```

### vibe3 run --publish 完成后

1. 确认 PR 已创建 → 展示 URL
2. 检查 CI 状态
3. CI 失败 → **分析失败原因，修复代码，push 更新**

报告：
```
PR 已创建：https://github.com/.../pull/XXXX
- CI：通过 / 修复中 / 失败（原因）
```

## Step 4: 向用户报告 + 循环

每步修正完成后，向用户报告**修正了什么**和**当前状态**：

```
Issue #XXXX 进度：
- [x] plan：通过（修正了 1 处范围遗漏）
- [x] run：通过（修复了 2 个测试失败）
- [ ] review：等待执行
- [ ] publish：等待

下一步：执行 vibe3 review
```

**只在以下情况询问用户**：
- 修正涉及设计决策（需要选择方案）
- 修正影响范围超出 issue 描述
- 用户明确要求暂停
- 修正多次失败（同一问题修 2 次仍未解决）

**不询问用户的情况**（直接修正继续）：
- 测试失败 → 修复代码
- 逻辑错误 → 修正逻辑
- 类型错误 → 修正类型
- lint/format 问题 → 自动修复

## Step 5: 循环

回到 Step 2 执行下一步，直到 PR 创建完成。

## vibe3 标准流程命令

```bash
vibe3 plan --branch <b>                  # 生成计划
vibe3 handoff show @plan --branch <b>    # 读取计划

vibe3 run --branch <b>                   # 执行实现
vibe3 handoff show @report --branch <b>  # 读取报告

vibe3 review --branch <b>                # 代码审查
vibe3 handoff show @audit --branch <b>   # 读取审查

vibe3 run --publish --branch <b>         # 创建 PR
```

- `--branch` 接受分支名或 issue 编号
- 异步命令用 Monitor 监控，不要轮询

## 与其他 workflow 的等效关系

| vibe-continue | superpowers | openspec |
|---------------|-------------|----------|
| `vibe3 plan` | `writing-plans` | `openspec:continue` |
| `vibe3 run` | `executing-plans` | `openspec:apply` |
| `vibe3 review` | `requesting-code-review` | `openspec:verify` |
| `vibe3 run --publish` | `finishing-a-development-branch` | `openspec:archive` |

## 限制

- 每步必须审查 + 修正，不能跳过直接进入下一步
- 明确问题直接修正，不报告后继续跑
- 模糊问题才询问用户
- 同一问题修正 2 次仍失败 → 暂停，向用户报告
- 不把 handoff 当真源（先看 flow show）
- Monitor 完成后立即 TaskStop 清理，不留残留
- 每次循环只保留一个活跃 Monitor 和一个 ScheduleWakeup
