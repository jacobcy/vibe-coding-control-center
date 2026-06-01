# Flow Blocked vs Bind Dependency：现状梳理与统一方向分析

**日期**：2026-05-15  
**文档类型**：现状分析  
**目标问题**：梳理 `vibe3 flow bind --role dependency`、`vibe3 flow blocked --task`、`blocked_reason`、`blocked_by_issue` 与 Orchestra 派发之间的真实关系，并明确当前不统一点，为后续执行文档提供依据。

---

## 执行摘要

当前实现里，`vibe3 flow bind --role dependency` 和 `vibe3 flow blocked --task` **已经部分复用同一底层逻辑**，都走到 `FlowService.block_flow()`，最终都会：

- 在 `flow_issue_links` 写入 `issue_role='dependency'`
- 在 `flow_state` 写入 `blocked_by_issue`
- 把 task issue label 切到 `state/blocked`
- 写入 `flow_blocked` 事件

但两者**不能简单视为“完全等价”**，原因有三：

1. `flow bind --role dependency` 是“绑定依赖 + 触发 blocked 副作用”的兼容入口，路径上有冗余 `link_issue()` 调用。
2. `flow blocked --task --reason ...` 会同时写 `blocked_reason`，而当前 Orchestra 会把 `blocked_reason` 视为**人工阻塞信号**，优先级高于 dependency auto-unblock。
3. `--branch` / `--pr` 是“定位当前要改哪条 flow”的参数，不是“阻塞原因”的一部分；真正的阻塞语义参数只有 `--reason`、`--task` 和历史别名 `--by`。

因此，**当前框架不是完全混乱，但也没有真正统一**。  
更准确的描述是：

- `flow_issue_links(role='dependency')`：依赖关系真源
- `blocked_by_issue`：当前主阻塞 issue 的显示/快捷字段
- `blocked_reason`：人工阻塞或诊断性阻塞原因
- `flow bind --role dependency`：历史兼容入口
- `flow blocked --task`：更接近统一 blocked 入口，但和 `--reason` 混用时会改变语义

---

## 一、当前代码中的真实执行路径

### 1.1 `vibe3 flow bind <issue> --role dependency`

入口：`src/vibe3/commands/flow_manage.py:bind()`

当前逻辑：

1. `TaskService.link_issue(branch, issue_number, role="dependency")`
   - 写 `flow_issue_links`
   - 视情况写 `issue_linked` 事件
2. 因为 `role == "dependency"`，继续调用：
   - `FlowService.block_flow(branch, blocked_by_issue=issue_number, actor=None)`
3. `block_flow()` 内部再次执行：
   - `TaskService.link_issue(branch, issue_number, role="dependency")`
   - 写 `flow_state.blocked_by_issue`
   - 若有 `reason` 才写 `blocked_reason`
   - task issue 切到 `state/blocked`
   - 若有 `reason` 才加 comment
   - 写 `flow_blocked`

结论：

- 这条路径**已经在行为上委托给 `block_flow()`**
- 但不是纯 alias，因为它在进入 `block_flow()` 之前先手动做了一次 `link_issue()`
- 这导致依赖写入存在**重复调用但大体幂等**

### 1.2 `vibe3 flow blocked --task <issue>`

入口：`src/vibe3/commands/flow_lifecycle.py:blocked()`

当前逻辑：

1. 解析目标 flow：
   - `--branch` 直接指定 branch
   - `--pr` 先解析 PR head branch
   - 默认使用当前分支
2. 解析阻塞参数：
   - `blocked_by_issue = task if task is not None else by`
3. 调用：
   - `FlowService.block_flow(branch, reason=reason, blocked_by_issue=blocked_by_issue)`
4. `block_flow()` 内部：
   - 若 `blocked_by_issue` 存在，则写 dependency link
   - 写 `flow_state.blocked_by_issue`
   - 若 `reason` 存在，则写 `blocked_reason`
   - task issue 切到 `state/blocked`
   - 若 `reason` 存在，则加 comment
   - 写 `flow_blocked`

结论：

- 这是当前最接近“统一 blocked 入口”的 CLI
- `--task` 与 `--by` 在这里是同义参数
- `--branch` / `--pr` 只负责定位 flow，不表达阻塞类型

### 1.3 现状对比

| 维度 | `flow bind --role dependency` | `flow blocked --task` |
|------|-------------------------------|------------------------|
| 入口职责 | 绑定 issue role | 设置 blocked 状态 |
| 是否复用 `block_flow()` | 是 | 是 |
| 是否写 dependency link | 是 | 是 |
| 是否写 `blocked_by_issue` | 是 | 是 |
| 是否可能写 `blocked_reason` | 否（当前调用不传 `reason`） | 是（如果传 `--reason`） |
| 是否切 `state/blocked` | 是 | 是 |
| 是否加 comment | 否（当前无 `reason`） | 仅有 `--reason` 时 |
| 是否有多余 `link_issue()` | 有 | 无 |

---

## 二、当前数据模型的真实语义

### 2.1 `flow_issue_links`

表意：**完整依赖关系真源**

```text
branch + issue_number + issue_role='dependency'
```

它回答的问题是：

- 当前 flow 依赖哪些 issue？
- Orchestra 应该检查哪些 dependency 是否满足？

这是 dependency 机制的主真源，不是 `blocked_by_issue`。

### 2.2 `blocked_by_issue`

表意：**当前主阻塞 issue 的快捷字段**

它回答的问题是：

- 这个 flow 现在主要被哪个 issue 挡住？
- UI / status / unblock 时优先展示哪个 blocker？

它不是完整 dependency 集合，只能表示一个“主 blocker”。  
如果一个 flow 有多个 dependency，完整集合仍然只能看 `flow_issue_links`。

### 2.3 `blocked_reason`

表意：**人工阻塞或诊断性阻塞原因**

当前代码里，`QualifyGateService.run_qualify_gate()` 会先看 `blocked_reason`：

- 只要 `blocked_reason` 非空，直接视为 blocked
- 不继续进入 dependency auto-unblock 分支

这意味着当前系统实际把 `blocked_reason` 当作：

- 人工阻塞说明
- 执行失败说明
- 需要人工确认后再恢复的阻塞信号

而不是“dependency 附带说明文字”。

这点非常关键，因为它决定了下面这件事：

```bash
vibe3 flow blocked --task 218 --reason "需要 #218 先完成"
```

在当前实现里，这**不是**“纯 dependency block + 可读文案”，而是：

- 写 dependency link
- 写 `blocked_by_issue = 218`
- 同时再写 `blocked_reason`
- 结果被 Orchestra 当成 manual block 优先处理

也就是说，这条命令会改变 unblock 语义。

---

## 三、Orchestra 当前到底如何处理 blocked

### 3.1 当前 gate 顺序

入口：`src/vibe3/domain/qualify_gate.py:run_qualify_gate()`

当前顺序是：

1. 先检查 `blocked_reason`
2. 再检查 dependency links 是否都已满足
3. 若满足且当前是 dependency block，则自动清理 blocked 元数据并恢复目标状态

这个顺序意味着：

- `blocked_reason` 的语义强于 dependency
- dependency auto-unblock 只适用于“没有人工 blocked_reason”的 blocked flow

### 3.2 dependency 数据从哪里来

当前 dependency 检查不是从 `blocked_by_issue` 开始，而是：

1. 先根据 task issue 找到对应 flow
2. 再从 `flow_issue_links` 取出所有 `role='dependency'` 的 issue
3. 对每个 dependency 调 GitHub 查看是否 `state == "closed"`

所以 Orchestra 真正依赖的是：

- `flow_issue_links`：完整 dependency 集合
- `blocked_by_issue`：补充展示 / unblock 元数据

### 3.3 自动恢复条件

当前自动恢复只在以下条件下发生：

- `blocked_reason` 为空
- dependency links 全部满足
- 当前 flow 处于 blocked 相关状态

恢复时会：

- 清 `blocked_by_issue`
- 清 `blocked_reason`
- 写 `flow_unblocked`
- 把 task issue 从 `state/blocked` 切回推断目标状态

因此，当前机制确实已经有“收集 blocked flow，派发前再检查能否解封”的雏形，但它不是只看 issue 关闭与否，还会被 `blocked_reason` 短路。

---

## 四、你提出的统一方向，与现状的关系

### 4.1 “`flow bind --role dependency` 只作为兼容层，背后统一到 `flow blocked --task`”

这个方向是合理的，而且**和当前代码趋势一致**。

原因：

- 现在 `flow bind --role dependency` 本来就会落到 `block_flow()`
- 它和 `flow blocked --task` 的差异主要只剩：
  - 命令表意不同
  - 前置多做了一次 `link_issue()`

更清晰的未来结构应当是：

- `flow bind --role task|related`：保留为 issue role 绑定入口
- `flow bind --role dependency`：兼容入口，内部直接转发到统一的 dependency-block 逻辑
- 统一 blocked 真入口：`flow blocked --task`

### 4.2 “`flow blocked --task / --pr / --by / --branch` 是否都统一到一个逻辑上”

这里需要拆开看：

- `--task`
  - 是阻塞语义的一部分
  - 表示“被哪个 issue 阻塞”
- `--by`
  - 当前只是 `--task` 的重复别名
  - 适合废弃
- `--branch`
  - 不是阻塞语义
  - 只是“这次要修改哪条 flow”
- `--pr`
  - 也不是阻塞语义
  - 只是“通过 PR 找到 branch”

所以更准确的统一方式不是“都统一成 `--task`”，而是分成两组：

1. **目标 flow 定位参数**
   - `--branch`
   - `--pr`
   - 默认当前 branch
2. **blocked 语义参数**
   - `--reason`
   - `--task`
   - `--by`（待废弃）

你的方向是对的，但要避免把“定位目标 flow”和“描述为什么 blocked”混成一类参数。

### 4.3 “manager 标准：具体原因用 `--reason`，被 issue 阻塞用 `--task`”

这个规则本身是清晰的，但和**当前实现**有一个冲突：

- 当前 `--reason` 会把 flow 变成 manual block 语义
- 当前 `--task` 才是 dependency block 语义

所以如果未来要采用你这个规则，需要进一步明确：

#### 方案 A：`--reason` 与 `--task` 互斥

含义：

- `--reason` = 人工阻塞，需要手动恢复
- `--task` = 依赖阻塞，可自动恢复

优点：

- 语义最干净
- 和当前 Qualify Gate 的优先级天然一致

代价：

- 不能写“依赖 issue + 补充原因文字”

#### 方案 B：允许同时传，但重定义语义

含义：

- `--task` = auto-unblock 真源
- `--reason` = 纯展示说明，不阻断 auto-unblock

优点：

- 表达能力强
- manager prompt 可读性更好

代价：

- 需要改当前 gate 逻辑
- 需要把 `blocked_reason` 拆分，或引入新字段区分：
  - manual_block_reason
  - dependency_note

当前代码**不是**方案 B，而更接近方案 A，只是 CLI 没有强制互斥，导致语义混杂。

### 4.4 “Orchestra 只收集 blocked flow，派发前检查 blocked reason 是否消除、blocked issue 是否关闭”

这个方向也是合理的，而且和当前实现已经部分一致：

- 当前 Qualify Gate 已经在派发前检查 blocked 条件
- 当前也已经会检查 dependency issue 是否 closed

但还有一个必须说清的点：

- `blocked_reason 是否消除` 不是自动可判定条件
- 它本质上还是“人工是否确认可继续”的信号

所以对 Orchestra 来说：

- `blocked issue 是否关闭` 可以自动判断
- `blocked_reason 是否消除` 只能依赖显式清除或明确状态迁移

换句话说，未来即使统一成“先收集 blocked flow，再派发前检查”，也应该保留这条边界：

- dependency block：自动判断、自动恢复
- manual block：显式清除后才允许恢复

---

## 五、当前框架到底哪里不统一

### 5.1 命令入口不统一

现状：

- `flow bind --role dependency` 能创建 dependency block
- `flow blocked --task` 也能创建 dependency block

问题：

- 同一件事有两个入口
- 一个是“role 绑定”的命令，一个是“状态设置”的命令
- 用户和 manager prompt 都容易混淆

### 5.2 `blocked_reason` 同时承担了两种职责

现状：

- 它既记录人工 blocked 原因
- 也可能被拿来描述 dependency blocked

问题：

- 当前 gate 把它当 manual block 信号
- 所以只要 dependency block 也写了它，就会改变恢复行为

这是现在最核心的不统一点。

### 5.3 `blocked_by_issue` 不是 dependency 真源，却经常被误读成真源

现状：

- 真正的 dependency 集合在 `flow_issue_links`
- `blocked_by_issue` 只是一个主 blocker 字段

问题：

- 容易被文档和调用方误写成“依赖关系真源”
- 这会掩盖多依赖场景

### 5.4 `--by` 没有独立存在价值

现状：

- `--by` 与 `--task` 完全同义

问题：

- 增加学习成本
- 没带来额外语义

---

## 六、对后续执行文档的建议边界

这份文档只描述现状。  
如果后续要写“统一 blocked 策略”的执行文档，建议明确回答以下问题：

### 6.1 统一后的 blocked 语义模型

至少要先选定下面两种之一：

1. `--reason` = manual block，`--task` = dependency block，两者互斥
2. `--task` 为 blocker 真源，`--reason` 只做展示，不阻断 auto-unblock

如果选 2，就不能继续复用当前 `blocked_reason` 语义，必须重构字段或 gate。

### 6.2 `flow bind --role dependency` 的去留

建议方向：

- 保留 CLI 兼容性
- 语义上降级为兼容别名
- 内部统一转发到同一个 dependency-block service

### 6.3 blocked flow 的收集与恢复策略

建议执行文档明确：

- Orchestra 收集对象是否统一为 `state/blocked`
- dependency block 的自动恢复条件
- manual block 的清除入口
- 当一个 flow 同时存在 dependency 和 manual reason 时，以谁为准

### 6.4 manager prompt 的标准动作

后续可以收敛成类似规则：

- 有外部 issue 作为前置依赖：用 `--task`
- 有纯文本阻塞原因，需要人工确认：用 `--reason`
- 两者是否允许并存，必须由执行文档定死

---

## 七、结论

当前实现并不是“`flow bind --role dependency` 和 `flow blocked --task` 在写完全不同的数据库字段”，这一点需要纠正。

更准确的现状是：

- 两者都写 `flow_issue_links(role='dependency')`
- 两者都写 `blocked_by_issue`
- 两者都走 `block_flow()` 这条主路径
- 真正不统一的是 `blocked_reason` 的职责，以及 dependency block 是否允许附带 `reason`

因此，你提出的统一方向总体上是成立的：

- 把 `flow bind --role dependency` 收敛成兼容层
- 把 dependency blocked 的主入口收敛到 `flow blocked --task`
- 让 Orchestra 统一在 blocked 队列里做派发前解封判断

但要真正清晰，必须先解决一个架构问题：

**`blocked_reason` 到底是“人工阻塞真源”，还是“所有 blocked 的通用说明字段”？**

在这个问题没有被重新定义之前，当前框架仍然会在 `--task` 和 `--reason` 混用时产生语义冲突。

这也是后续执行文档最需要先定死的核心决策。
