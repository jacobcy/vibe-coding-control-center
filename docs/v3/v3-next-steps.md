# V3 Next Steps Roadmap

**日期**: 2026-03-22
**状态**: 收敛中
**定位**: 本轮 handoff / review explainability 收口后的后续路线图，聚焦 GitHub label 编排与质量治理能力补齐

> 新增目标与能力缺口文档：
> - [GitHub Label 多 Agent 编排目标](../prds/github-label-agent-orchestration-target.md)
> - [GitHub Label 多 Agent 编排能力缺口](../prds/github-label-agent-orchestration-gaps.md)

---

## 1. 当前判断

### 1.1 已经收敛的部分

- `flow` 本地执行现场已经基本可用：
  - `flow new / bind / show / list`
  - `flow_state` 已承接 `task_issue_number / pr_number / *_ref / next_step / blocked_by / actor`
- `handoff` 已收敛为中间态，而不是第二真源：
  - SQLite 只做最小索引
  - `.git/vibe3/handoff/<branch-safe>/current.md` 做结构化交接缓冲区
- review 风险链路已经改成 inspect-based：
  - `review.auto_trigger` 已从配置真相入口移除
  - `pre-push` / `pr ready` 现在都能输出原因、扣分项、建议
- `vibe3 inspect structure` 已具备结构信息入口：
  - 可以做单文件结构分析
  - 可以输出 `src/vibe3` 的目录级结构摘要
  - 但还不是 snapshot / diff 版本

### 1.2 还没打通的部分

当前真正没通的是：

- 基于 GitHub label 的 agent 编排状态机
- `issue -> flow -> handoff -> pr` 的多 agent 协同协议
- GitHub Project 作为编排 UI 的稳定映射
- `structure / snapshot / diff` 的质量控制闭环

现在的 `flow` 更像本地执行现场，`issue_role` 更像关系真源，但“远端状态机”和“质量治理闭环”还没有接上。

---

## 2. 主链现状

### 2.1 当前可运行主链

当前代码能跑通的是这条：

`issue(role) -> flow -> local handoff/index -> pr`

也就是说：

- issue 已能通过 `flow bind` / `task link` 进入本地关系层
- branch 上可以创建和绑定 flow
- flow 可以记录当前现场状态
- handoff 可以给 planner / executor / reviewer 传递中间上下文
- PR 可以写回本地 flow 最小责任链

### 2.2 仍然断开的桥接链

目标要的完整链是：

`issue -> label 状态机 -> flow -> handoff -> pr -> Project UI`

当前断点在三段：

- `issue_role -> GitHub label` 的自动化镜像
- `label 状态机 -> Project UI` 的稳定映射
- `flow / handoff / pr` 与编排状态的联动协议

所以现在不能说“GitHub 原生编排已通”，只能说“本地 flow runtime 基本通，远端状态机与质量治理还未闭环”。

---

## 3. 远端同步与自动化缺口

### 3.1 缺的不是 flow sync

当前最容易跑偏的误区是去做：

- `flow sync`
- 本地 task 镜像缓存
- 本地长期 task registry

这些都不应该成为下一步重点。

### 3.2 真正缺的是三类能力

#### A. label state machine

职责：

- 定义 issue 当前是否可领取、是否执行中、是否阻塞、是否待 review、是否待 handoff
- 给 agent 和人类管理者提供统一的阶段信号

边界：

- 不承载复杂上下文
- 不反向定义 `task/related/dependency`
- 不替代 handoff 记录细节

#### B. GitHub Project UI bridge

职责：

- 将 label 状态机映射为 GitHub Project 视图
- 让管理者实时看到任务在 flow 循环中的位置

本地允许保留：

- 远端 identity 与最小索引
- Project 视图所需的稳定映射规则
- 当前执行所需的只读 bridge 字段

本地不允许保留：

- Project 作为第三套状态机
- 编排状态的长期本地镜像真源
- 与 labels 冲突的额外阶段定义

#### C. handoff / review / PR 联动

职责：

- 让 handoff 成为进入某些状态前的必备交接动作
- 让 review / PR / merge 消费统一后的编排状态
- 让自动化能检查“是否该写 handoff、是否可进入下一阶段”

边界：

- 不把 handoff 变成正文型数据库
- 不让 PR 流程重新定义状态机

---

## 4. Structure Snapshot 的位置

`docs/v3/structure/design-proposal.md` 的方向本身是对的：

- 从单文件 AST 分析升级到项目级 structure snapshot
- 给 review、handoff、未来 orchestrator 提供稳定结构上下文

当前需要特别澄清的是：

- **已经存在**：`vibe3 inspect structure`
- **当前能力**：文件级分析 + `src/vibe3` 摘要
- **尚未完成**：`build / show / diff` 驱动的 snapshot system

所以 Step 4 不是从 0 到 1 发明 structure inspect，而是在现有 `vibe3 inspect structure` 基础上补齐 snapshot / diff。

但它也不该早于 label 状态机和交接协议。

### 4.1 原因

- label 状态机解决的是“谁在做、做到哪”
- handoff 协议解决的是“如何安全换手”
- `structure snapshot` 解决的是“产出有没有失控”
- 没有前两者，snapshot 只能做分析工具，不能成为编排闭环的一部分

### 4.2 合适顺序

正确顺序应该是：

1. 先补 `label state machine`
2. 再补 `handoff / review / PR` 联动协议
3. 再补 `Project UI bridge`
4. 再做 `structure snapshot / diff`
5. 最后进入 `orchestrator`

---

## 5. 后续路线图

### Step 1: 定义 GitHub Label 编排状态机

**目标**

让 issue / flow / handoff / pr 进入统一的可观测状态机，而不是继续靠隐式约定协作。

**要做的事**

- 定义 label 状态集合
- 定义状态迁移规则
- 定义 agent 认领 / 释放 / 交接规则
- 定义 issue-role 与 label-state 的边界

**完成标志**

- agent 能通过 label 判断何时进入、何时退出
- 不再把 `task/related/dependency` 和编排阶段混成一套语义

### Step 2: 打通 Handoff / Review / PR 协同协议

**目标**

让 handoff 成为可执行的换手协议，而不是“写了也可以不用”的补充文本。

**要做的事**

- 定义进入 blocked / handoff / review 前的 handoff 要求
- 定义接手方读取 handoff 的最小约束
- 定义 PR / merge / close 如何消费编排状态
- 定义 review explainability 与状态迁移的联动

**完成标志**

- handoff 成为标准交接动作
- review / PR / merge 不再绕过状态机各自演化一套语义

### Step 3: 落地 GitHub Project UI Bridge

**目标**

让 GitHub Project 成为编排 UI，而不是另一套隐式状态容器。

**要做的事**

- 定义 label 状态到 Project 视图的映射
- 定义人工管理者观察面板
- 定义最小只读 bridge 字段
- 禁止 Project 重新定义阶段语义

**完成标志**

- 管理者能通过 Project 直接看到 flow 循环位置
- Project 成为 UI，而不成为第三真源

### Step 4: 落地 Structure Snapshot 最小版

**目标**

给 review / handoff / future orchestrator 提供稳定结构上下文，并建立最小质量治理闭环。

**建议范围**

第一版只做：

- 保留 `vibe3 inspect structure` 作为 V3 入口
- 在现有 file-level / summary 能力上补 `build`
- 在现有 file-level / summary 能力上补 `show`

第二版再做：

- `diff`
- 与状态迁移和 review 触发点联动

更后面再做：

- duplication detection

**完成标志**

- `vibe3 inspect structure` 不再只是文件摘要，而是可生成、可读取结构快照
- structure diff 可被 review/handoff 消费

### Step 5: 进入多 Agent Orchestrator 与垃圾代码回收设计

**目标**

基于已稳定的状态机、交接协议和质量信号，规划多 agent 编排与代码回收闭环。

**前置条件**

- `label state machine` 已稳定
- `Project UI bridge` 已稳定
- `handoff` 中间态协议稳定
- `structure snapshot` 可提供结构上下文
- flow / pr / review 语义不再漂移

**完成标志**

- orchestrator 只做编排，不再反向改写对象定义
- 垃圾代码回收成为状态机中的正式能力，而不是事后 cleanup

---

## 6. 下一轮执行建议

下一轮不要并行扩太多面，建议只做一个主题：

### 推荐主题

`Label State Machine + Handoff Protocol`

### 不建议抢跑的主题

- 不要先做全量 orchestrator
- 不要先做全量 structure diff
- 不要重新发明本地 task store
- 不要把 handoff 扩成正文型数据库

---

## 7. 命令面边界

为避免把 V2 / V3 搞混，当前命令面应明确区分：

- `vibe` = V2 shell 入口
- `vibe3` = V3 Python 入口

在 structure / inspect 这条线上，应统一按 V3 入口表述为：

- `vibe3 inspect structure`
- `vibe3 inspect symbols`
- `vibe3 review ...`

---

## 8. 结论

这一轮结束时，v3 的真实状态应当这样描述：

- `flow runtime` 基本通了
- `handoff` 已回到正确边界
- `review explainability` 已补齐
- `issue_role` 关系语义已基本收敛
- 下一优先级是 `Label State Machine + Handoff Protocol`
- `Structure Snapshot` 是质量治理基础设施，不应早于状态机与交接协议
- `Orchestrator` 必须建立在状态机、UI bridge 和质量闭环稳定之后
