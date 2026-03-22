# GitHub Label 多 Agent 编排目标

**创建时间**: 2026-03-22
**状态**: Draft
**定位**: 定义 V3 下一阶段的目标系统，不展开实现细节，只定义目标状态

---

## 1. 目标一句话

以 **GitHub issue** 为任务锚点，以 **GitHub label** 作为轻量状态机，以 **handoff** 作为执行上下文与交接通道，以 **GitHub Project 视图** 作为 UI 界面，构建一套可观测、可交接、可审计的轻量级多 agent 编排系统。

同时，这套系统必须内建 **structure / snapshot / diff** 质量控制能力，不只编排 agent 推进任务，也要持续识别和回收垃圾代码。

---

## 2. 目标系统的核心对象与真源分层

### 2.1 GitHub issue

- 是任务身份锚点
- 承载需求、约束、讨论和最终交付目标
- agent 不发明新对象，围绕 issue 工作

### 2.2 GitHub label

- 是编排状态机信号
- 用于表达 issue 当前所处阶段
- 用于表达 agent 是否可认领、是否执行中、是否阻塞、是否待 review、是否待 handoff
- 是多 agent 协调的远端真源

### 2.3 flow

- 是 branch 对应的执行现场
- 是 issue 在本地 runtime 中的执行容器
- 承载当前 task 指针、refs、next_step、blocked_by、actor 等最小执行信息
- 承载 issue 与当前 flow 的本地关系信息，但不替代 GitHub 状态机

### 2.4 handoff

- 是上下文和交接通道
- 不是真源
- 保存当前 agent 的执行说明、下一步、阻塞点、风险、待接手信息
- 只解释“为什么停在这里、下一步怎么接”，不定义“当前处于哪个状态”

### 2.5 GitHub Project

- 是 UI 和可观测面板
- 用视图展示 issue 在编排循环中的位置
- 不再发明第三套状态机

### 2.6 structure / snapshot / diff

- 是质量控制层
- `structure` 看结构是否越界、膨胀、错层
- `snapshot` 保留阶段性结构基线
- `diff` 审计 agent 改动是否偏离目标

### 2.7 真源分层

- GitHub issue：任务身份真源
- SQLite `flow_issue_links.issue_role`：issue 与 flow 关系真源
- GitHub labels：编排状态真源
- handoff：交接上下文，不是真源
- GitHub Project：UI 视图，不是真源
- structure / snapshot / diff：质量审计真源

---

## 3. 目标主链

目标主链不是单纯的 `issue -> pr`，而是：

`issue -> label 状态机 -> flow 执行 -> handoff 交接 -> pr -> merge/done`

其中：

- `issue` 提供任务身份
- `label` 提供调度和阶段信号
- `flow` 提供本地执行现场
- `handoff` 提供上下文连续性
- `pr` 提供交付出口

---

## 4. 多 Agent 编排目标

### 4.1 认领

- agent 通过 labels 判断 issue 是否可领取
- 认领动作必须可见、可冲突检测、可回放

### 4.2 执行

- agent 在 flow 内推进任务
- agent 必须持续写回 handoff
- agent 的执行位置必须能通过 GitHub 界面观察

### 4.3 交接

- handoff 是标准交接协议
- 新 agent 接手前，先读 handoff，再核对 flow / git / issue 现场

### 4.4 退出

- issue 进入 review / blocked / done / merged 时，状态机必须明确
- 不能让多个 agent 在语义不清的状态下重复推进

---

## 5. Label 状态机目标

Label 应承担两类职责：

### 5.1 编排状态

- 待领取
- 已认领
- 执行中
- 阻塞
- 待交接
- 待 review
- 可合并
- 已完成

### 5.2 协调信号

- 当前是否允许新 agent 进入
- 当前是否要求 handoff
- 当前是否要求 review
- 当前是否要求人工介入

**关键约束**：

- label 只表达有限状态，不承载复杂上下文
- 复杂说明必须进 handoff
- GitHub Project 视图只消费这套状态，不重定义状态
- 标签自动化只镜像和推进编排状态，不反向改写 issue-role 关系

---

## 6. 质量控制目标

多 agent 编排不是唯一目标，代码质量回收同样是目标系统的一部分。

### 6.1 structure

- 识别模块边界是否失控
- 识别文件是否膨胀
- 识别调用关系是否污染

### 6.2 snapshot

- 在关键阶段形成结构快照
- 允许 review / handoff / orchestrator 消费同一份结构基线

### 6.3 diff

- 对比两个快照或两个阶段的结构变化
- 判断 agent 是否引入垃圾代码、漂移实现、越权改动

### 6.4 垃圾代码回收

- 垃圾代码回收不是额外 cleanup
- 而是编排系统的内建职责
- agent 不只负责生成代码，也必须支持识别和回收低质量改动

---

## 7. 真源与边界目标

### 7.1 真源原则

- issue 身份真源在 GitHub issue
- issue 与 flow 的关系真源在 SQLite `issue_role`
- 编排状态真源在 GitHub label 状态机
- 执行上下文真源在 flow runtime + handoff 的边界组合
- 质量判断真源在 structure / snapshot / diff

### 7.2 禁止事项

- 不做第二套隐藏调度系统
- 不让 Project 变成第三套状态机
- 不让 handoff 变成正文型数据库
- 不让 label 承载复杂上下文
- 不让 label 反向定义 `task/related/dependency`
- 不让质量控制依赖口头约定

---

## 8. 目标完成标志

达到以下状态时，说明目标系统成立：

1. 人和 agent 都能从 GitHub 界面直接看到任务当前阶段
2. agent 能通过 label 协议安全认领和推进任务
3. handoff 能支撑可靠交接，不需要依赖隐式记忆
4. Project 视图能实时反映 flow 循环位置
5. structure / snapshot / diff 能对 agent 改动做结构级审计
6. 垃圾代码回收成为标准流程的一部分，而不是事后补救

---

## 9. 这份目标文档不解决什么

这份文档不定义：

- 具体 label 名称
- 具体状态迁移表
- 具体 GitHub Actions 工作流
- 具体 handoff 文件格式细节
- 具体 structure snapshot 子命令设计

这些内容应放到“能力缺口与实施计划”中展开。
