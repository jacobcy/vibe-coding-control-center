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

**任务类型判断**（进入流程前的第一步）：

```
flow 有 plan/run/review_ref?
  ├─ 有 → 恢复已有状态（标准实现流程）
  └─ 无 → 检查 issue 标签
       ├─ roadmap/rfc → 进入 RFC 探索模式（见下方）
       ├─ roadmap/design → 进入 RFC 探索模式
       ├─ roadmap/epic → 不在此处处理，请使用 /vibe-new 选择 sub-issue
       └─ 其他 → 标准实现流程
```

- `roadmap/rfc` 和 `roadmap/design` 标签的 issue 自动走 RFC 探索模式
- 用户明确说"探索/研究/分析"等关键词时也进入探索模式
- 探索模式不执行 `vibe3 plan`/`vibe3 run`/`vibe3 review`

---

## RFC 探索模式

**适用于**：`roadmap/rfc`、`roadmap/design` 标签的 issue，或用户明确要求探索/研究/分析的任务。

**目标**：探索问题空间、质询假设、比较方案、形成结论。**不产生代码实现**。

### 探索流程

```
Explore (了解领域) → Analyze (逐项质询) → Converge (收敛结论) → Record (记录输出)
```

### Grill-Me 质询思想

探索模式的灵魂是苏格拉底式质询 — "烤"问每个假设和方案：

```
质询维度：
  ├─ 假设质询  "这个假设成立吗？证据是什么？不成立会怎样？"
  ├─ 边界扫描  "我们忽略了什么边界情况？极端条件下会怎样？"
  ├─ 代价分析  "这个方案的代价是什么？（复杂度/维护/性能/学习成本）"
  ├─ 逆向思考  "如果这个方案是错的，会怎样？反例是什么？"
  ├─ 简化挑战  "有更简单的方案吗？我们是不是在做过度工程？"
  └─ 替代追问  "还有其他方案吗？为什么选这个不选那个？"
```

### Step E1: Explore — 了解领域

并行执行：

```bash
vibe3 flow show [--branch <b>]
vibe3 handoff show @current [--branch <b>]
gh issue view <number> --json body,labels,comments
git status
```

然后：
1. **阅读 issue body 和相关资料** — 理解问题背景、相关文档、已有讨论
2. **阅读关键源码** — 定位核心文件和实现，画出当前架构
3. **Grill-Me 入门**：用以下问题"烤"自己：
   - "问题描述是否完整？有没有隐藏的前提？"
   - "issue 提到的问题在代码中真实存在吗？"
4. **输出**：领域理解 + 关键文件清单 + 初步问题列表

### Step E2: Analyze — 逐项质询

对每个子问题使用以下结构化分析：

```
  单点分析框架
  ==============================

  1. 现状描述
     "当前是什么情况？"

  2. 假设清单
     "隐含了哪些假设？"
     -> 逐条列出并标注可信度

  3. 质询 (Grill Me)
     a) "这个假设被违反会怎样？"
     b) "边界条件是什么？"
     c) "代价和收益是否匹配？"
     d) "有反例吗？"
     e) "更简单的做法是什么？"

  4. 方案发散
     "有哪些可能的方案？"
     -> 列出 2-3 种方案及其 trade-off

  5. 收敛
     "推荐哪个？理由是什么？"
     -> 明确推荐 + 开放问题
```

**使用指导**：
- issue 的每个子问题各走一轮 Analyze
- 发现新问题分支时新增一轮
- 一轮分析应控制在 3-5 次交互，不无限发散

### Step E3: Converge — 收敛结论

将各轮分析的结论汇总：

```
分析结论：
+ 已确认问题：N 个（每个附证据）
- 已排除问题：M 个（附排除理由）
? 开放问题：K 个（需进一步研究）
* 推荐方案：（如果有）
! 风险提示：（已知盲区）
```

**Grill-Me 终审**：
- "这些结论经得起反向质询吗？"
- "是否还有未考虑的第三方视角？"
- "如果半年后回看，这个结论会不会显得天真？"

### Step E4: Record — 记录输出

```bash
# 记录分析结论到 handoff
vibe3 handoff append "[vibe-continue] <分析结论摘要>" --actor vibe-continue --kind analysis
```

**可能的输出形式**：
- **Issue comment**：分析结论回写到 GitHub issue（明确方案或研究结论时）
- **ADR 记录**：关键设计决策需记录
- **Handoff**：中间分析状态保存
- **新 Issue**：发现了新的子问题 -> 告知用户创建新 issue

### Step E5: 探索出口

探索完成后，可转向以下方向：

```
探索完成？
+ 结论明确，可进入实现 -> 告知用户创建实现 issue 或继续 /vibe-new
+ 发现新问题 -> 告知用户创建新 issue
+ 需要决策 -> 告知用户结论，等待决策
+ 继续探索 -> 回到 Step E1 继续
```

### 探索模式报告格式

每步向用户报告探索进度：

```
RFC 探索进度 (Issue #XXXX):
- [x] E1 Explore: 已了解领域 (关键文件: N 个)
- [ ] E2 Analyze: 待分析 (剩余 M 个子问题)
- [ ] E3 Converge: 待收敛
- [ ] E4 Record: 待记录

当前发现：
- 问题 A: 确认存在（证据: ...）
- 问题 B: 需进一步研究

下一步：继续 Analyze 子问题 X
```

---

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

## Step 2: 判断流程 + 执行下一步

### 流程判断

先判断任务类型：

```
当前是 RFC 探索模式？
  ├─ Yes → 执行 RFC 探索流程（Step E1-E5，参见上方 RFC 探索模式章节）
  └─ No  → 执行标准实现流程（plan → run → review → publish，如下）
```

### 标准实现流程

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

**Fallback**：如果接管后实现遇到困难（上下文不足、能力限制），建议重新执行 `vibe3 run`（可能需要手动保存当前状态），而不是继续在当前 session 硬撑。

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

**ScheduleWakeup 与 Monitor 的关系**：
- ScheduleWakeup 是 **fallback**，不是并行 companion
- 正常流程：Monitor 完成正常 → ScheduleWakeup 不再需要（下次循环创建新的）
- 异常流程：Monitor 失败/超时 → ScheduleWakeup 触发作为 backup 唤醒 agent

**启动序列**：启动命令 → 创建 Monitor → 设置 ScheduleWakeup 作为 fallback

**禁止**：
- 同时运行多个 Monitor 监听同一命令
- Monitor 触发后不清理让它继续运行
- 让已超时的 Monitor 残留

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

**重复修复限制**：同一问题修正 2 次仍未解决 → 暂停，向用户报告（见 Step 4 和限制章节）

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

**重复修复限制**：同一问题修正 2 次仍未解决 → 暂停，向用户报告（见 Step 4 和限制章节）

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

标准实现流程报告：
```
Issue #XXXX 进度：
- [x] plan：通过（修正了 1 处范围遗漏）
- [x] run：通过（修复了 2 个测试失败）
- [ ] review：等待执行
- [ ] publish：等待

下一步：执行 vibe3 review
```

RFC 探索模式报告（见 RFC 探索模式章节的报告格式）。

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

| RFC 探索模式 | 等效能力 |
|--------------|----------|
| E1 Explore | `openspec-explore` 探索模式 |
| E2 Analyze (Grill Me) | 苏格拉底式质询 / 魔鬼代言人 |
| E3 Converge | 方案对比与收敛 |
| E4 Record | Issue comment / ADR 记录 |

## 限制

- 每步必须审查 + 修正，不能跳过直接进入下一步
- 明确问题直接修正，不报告后继续跑
- 模糊问题才询问用户
- 同一问题修正 2 次仍失败 → 暂停，向用户报告
- 不把 handoff 当真源（先看 flow show）
- Monitor 完成后立即 TaskStop 清理，不留残留
- 每次循环只保留一个活跃 Monitor 和一个 ScheduleWakeup
- **RFC 探索模式不产生代码实现**，仅输出分析结论和文档变更。如果探索过程中发现问题需要修复代码，应暂停探索模式，告知用户后进入标准实现流程