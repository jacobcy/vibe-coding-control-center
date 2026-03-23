# GitHub Label 多 Agent 编排能力缺口

**创建时间**: 2026-03-22
**状态**: Draft
**定位**: 对照目标系统，列出当前仓库离目标还缺什么能力

---

## 1. 当前结论

仓库已经具备：

- `issue -> flow -> pr` 的部分主链能力
- `flow new / bind / show / list`
- `task show / task bridge`
- 本地 handoff 作为中间态
- `vibe3 inspect structure` 作为结构分析入口

仓库还不具备：

- 基于 GitHub label 的正式状态机
- agent 认领 / 交接 / review / block 的统一编排协议
- 由 label 驱动的 GitHub Project 可视化编排界面
- 基于 snapshot / diff 的结构级质量控制闭环
- 把垃圾代码回收内建进编排流程的机制

---

## 2. 编排层能力缺口

### 2.1 Label 状态机缺失

当前缺口：

- 没有正式定义 label 状态集合
- 没有状态迁移规则
- 没有互斥关系与冲突规则
- 没有 agent 可消费的状态协议
- 没有 issue-role 与编排状态的边界说明

影响：

- agent 无法稳定判断何时认领、何时让出、何时交接
- GitHub Project 无法稳定展示流程位置

### 2.2 Agent 认领协议缺失

当前缺口：

- 没有 “可领取 / 已认领 / 已释放” 的标准语义
- 没有 agent 身份和 issue 占用关系的稳定表达
- 没有并发认领冲突处理
- 没有超时释放与人工接管规则

影响：

- 多 agent 协作容易重复推进
- 无法建立可靠的任务分配秩序

### 2.3 Handoff 与 Label 未打通

当前缺口：

- handoff 有内容，但和 label 状态迁移未形成协议
- 没有 “进入某状态前必须写 handoff” 的约束
- 没有 “读取 handoff 后才能接手” 的统一规则
- 没有 handoff 完整性校验

影响：

- handoff 存在，但无法成为编排系统的一部分
- 交接容易流于形式

### 2.4 Project 视图语义未定义

当前缺口：

- 没有把 label 状态映射到 Project 视图的正式规则
- 没有定义“哪个视图展示哪个阶段”
- 没有定义人类管理者如何通过 Project 判断 agent 所处位置
- 没有定义 Project 与自动化的最小字段契约

影响：

- Project 只能看“有无 item”，不能看流程位置
- 无法形成编排 UI

---

## 3. 对象边界与同步层能力缺口

### 3.1 issue-role 与 label-state 尚未分层固化

当前已经统一了 `task / related / dependency`，但还缺：

- `issue_role` 负责关系、`label` 负责阶段的正式边界
- 标签自动化只镜像关系、不反向改义的制度化约束
- PR / merge / close 行为如何消费这两层真源

影响：

- 很容易再次把 “关系” 和 “状态” 混成一套字段
- 标签自动化一上线就可能把本地关系和远端状态互相污染

### 3.2 issue / flow / pr 主链还不够编排化

当前已经有主链雏形，但还缺：

- issue 与 label 状态机的绑定
- flow 与当前 agent 状态的绑定
- pr 与编排阶段的联动

### 3.3 GitHub Project 还不是编排 UI

当前 GitHub Project 更接近规划视图或列表容器。

还缺：

- 基于 label 状态机的列/视图映射
- 基于 handoff / review / blocked 的观察面
- 管理者可直接判断 flow 循环位置的统一视图

---

## 4. 质量控制层能力缺口

### 4.1 structure 只有入口，没有治理闭环

当前已有：

- `vibe3 inspect structure`

还缺：

- 标准输出基线
- 可复用结构摘要
- 能挂到 handoff / review / orchestrator 的稳定消费格式
- 与 label 状态迁移的挂钩点

### 4.2 snapshot 缺失

当前缺口：

- 没有结构快照生成能力
- 没有阶段性基线
- 没有供 review / handoff 对照的结构版本

影响：

- 结构分析只能当场看，不能被编排系统反复消费

### 4.3 diff 缺失

当前缺口：

- 没有结构级 diff
- 没有基于 diff 的漂移检查
- 没有 agent 输出质量审计接口

影响：

- 无法判断 agent 是否引入结构级垃圾代码
- 无法把质量检查接入执行循环

### 4.4 垃圾代码回收机制缺失

当前缺口：

- 没有正式定义什么是“垃圾代码”
- 没有回收触发条件
- 没有回收优先级和补偿路径
- 没有把回收结果写回状态机或 handoff 的协议

影响：

- 多 agent 只会增加产出，不会增加系统自净能力

---

## 5. 文档与语义层缺口

### 5.1 术语虽已收敛，但还未形成编排标准

当前已统一：

- `issue`
- `task / related / dependency`
- `flow bind` / `task link`

还缺：

- label 状态机术语
- agent 编排状态术语
- handoff 与 label 的边界术语

### 5.2 目标与能力缺口需要分离维护

否则很容易再次发生：

- 把目标态写成现状
- 把未来自动化写成当前能力
- 把 GitHub 视图当成真源

---

## 6. 补齐顺序建议

### 第一阶段：编排协议最小闭环

先补：

1. label 状态集合
2. 状态迁移规则
3. agent 认领与释放规则
4. handoff 与状态迁移的联动要求

### 第二阶段：标签自动化与 Project 视图落地

再补：

1. issue-role 到标签的镜像规则
2. 编排状态到 Project 的视图映射
3. UI 分组规则与管理者观察面板

### 第三阶段：质量控制最小闭环

再补：

1. structure 输出稳定化
2. snapshot 最小版
3. diff 最小版
4. 回收触发规则

### 第四阶段：自动化执行

最后补：

1. label 自动更新
2. Project 自动归位
3. review / handoff 自动检查
4. 垃圾代码回收自动触发

---

## 7. 最关键的非功能要求

### 7.1 不做第二真源

- label 是编排状态机，不是正文数据库
- Project 是 UI，不是真源
- handoff 是上下文，不是真源

### 7.2 可观测

- 人类和 agent 都要能看见任务位置
- 必须能回答 “现在谁在做、做到哪、为什么卡住”

### 7.3 可交接

- 任何 agent 都必须可安全退出
- 另一个 agent 必须能低成本接手

### 7.4 可审计

- 必须能对 agent 输出做结构和 diff 审查
- 必须能追溯状态迁移与质量退化

### 7.5 可回收

- 系统必须支持清理低质量产出
- 不允许多 agent 编排变成“更快地产生垃圾代码”

---

## 8. 下一步建议

下一步建议不是直接写自动化，而是先补一份正式的：

**GitHub Label 状态机设计**

至少定义：

1. label 集合
2. 迁移表
3. 互斥规则
4. agent 认领规则
5. handoff 触发规则
6. Project 视图映射
7. structure / snapshot / diff 在各阶段的检查点
