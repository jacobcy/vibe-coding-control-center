# V3 Next Steps Roadmap

**日期**: 2026-03-21
**状态**: 收敛中
**定位**: 本轮 handoff / review explainability 收口后的后续路线图

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

### 1.2 还没打通的部分

当前真正没通的是：

- `task -> GitHub Project` 真源桥接
- `repo issue -> roadmap item -> task -> flow` 的完整桥接链
- 远端规划层同步到本地 bridge 的能力

现在的 `task` 仍然只是本地 execution bridge，不是完整的 GitHub Project task 实现。

---

## 2. 主链现状

### 2.1 当前可运行主链

当前代码能跑通的是这条：

`branch -> flow -> local handoff/index -> pr`

也就是说：

- branch 上可以创建和绑定 flow
- flow 可以记录当前现场状态
- handoff 可以给 planner / executor / reviewer 传递中间上下文
- PR 可以写回本地 flow 最小责任链

### 2.2 仍然断开的桥接链

标准要的完整链是：

`repo issue -> roadmap item(GitHub Project) -> task -> flow -> pr`

当前断点在中间两段：

- `roadmap item -> task`
- `task -> flow` 的远端真源对齐

所以现在不能说 task/flow 全通，只能说“flow runtime 基本通，task 真源桥接未完成”。

---

## 3. 远端同步缺口

### 3.1 缺的不是 flow sync

当前最容易跑偏的误区是去做：

- `flow sync`
- 本地 task 镜像缓存
- 本地长期 task registry

这些都不应该成为下一步重点。

### 3.2 真正缺的是两类能力

#### A. roadmap sync

职责：

- 把 GitHub Project items 同步到本地 roadmap mirror
- 只解决规划层 mirror，不解决 execution runtime

边界：

- 不做 task 正文缓存
- 不做 flow 状态裁定
- 不做 agent 交接存储

#### B. task bridge hydrate/read

职责：

- 从 GitHub Project item / roadmap item 读取 task 真值
- 映射成 flow 可消费的 execution bridge 信息

本地允许保留：

- 远端 item identity
- 关联 issue / spec / refs
- 当前执行所需最小 bridge 字段

本地不允许保留：

- task 正文主副本
- task 状态真源副本
- Project 全量镜像缓存

---

## 4. Structure Snapshot 的位置

`docs/v3/structure/design-proposal.md` 的方向本身是对的：

- 从单文件 AST 分析升级到项目级 structure snapshot
- 给 review、handoff、未来 orchestrator 提供稳定结构上下文

但它不该插到 `task -> GitHub Project` 打通之前。

### 4.1 原因

- `task bridge` 解决的是主链对象是否贯通
- `structure snapshot` 解决的是上下文是否更强
- 主链对象没打通前，先上 snapshot 只能提升分析能力，不能修补对象断层

### 4.2 合适顺序

正确顺序应该是：

1. 先补 `task -> GitHub Project bridge`
2. 再补 `roadmap sync / task hydrate`
3. 再做 `structure snapshot`
4. 最后进入 `orchestrator`

---

## 5. 后续四步路线图

### Step 1: 打通 Task 真源桥接

**目标**

让 `task` 正式接到 GitHub Project，而不是继续作为本地壳对象漂浮。

**要做的事**

- 定义 `task` 远端读取契约
- 明确 task 的本地 bridge 字段边界
- 明确哪些字段只能从 GitHub Project 实时读取
- 禁止本地写 task 真相状态

**完成标志**

- 能从远端 Project item 读取 task 真值
- 本地 `task` 命令不再伪装自己是 task 真源

### Step 2: 补齐规划层同步与桥接

**目标**

把 `repo issue -> roadmap item -> task -> flow` 真正串起来。

**要做的事**

- 做 `roadmap sync`
- 明确 roadmap item 与 task 的映射关系
- 让 flow 消费 task bridge，而不是直接承担 task 真相

**完成标志**

- 规划层和执行层之间的对象映射清晰
- 本地 flow 不再承担不该承担的规划职责

### Step 3: 落地 Structure Snapshot 最小版

**目标**

给 review / handoff / future orchestrator 提供稳定结构上下文。

**建议范围**

第一版只做：

- `file_analyzer` / `structure_service` 职责拆分
- `build`
- `show`

第二版再做：

- `diff`

更后面再做：

- duplication detection

**完成标志**

- 结构快照可生成、可读取、可被 review/handoff 消费

### Step 4: 进入 Orchestrator 设计

**目标**

基于已稳定的对象链与 handoff 协议，规划多 agent 编排。

**前置条件**

- `task -> GitHub Project` 已打通
- `handoff` 中间态协议稳定
- `structure snapshot` 可提供结构上下文
- flow/task/pr 语义不再漂移

**完成标志**

- orchestrator 只做编排，不再反向改写对象定义

---

## 6. 下一轮执行建议

下一轮不要并行扩太多面，建议只做一个主题：

### 推荐主题

`Task Bridge + Roadmap Sync`

### 不建议抢跑的主题

- 不要先做 orchestrator
- 不要先做全量 structure diff
- 不要重新发明本地 task store
- 不要把 handoff 扩成正文型数据库

---

## 7. 结论

这一轮结束时，v3 的真实状态应当这样描述：

- `flow runtime` 基本通了
- `handoff` 已回到正确边界
- `review explainability` 已补齐
- `task` 仍缺 GitHub Project 真源桥接
- 下一优先级是 `Task Bridge + Roadmap Sync`
- `Structure Snapshot` 是下一阶段基础设施，不应早于 task bridge
- `Orchestrator` 必须建立在以上三者稳定之后
