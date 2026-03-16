# Vibe3 并行重建计划 (Cleaned Battlefield)

本文档跟踪 Vibe3 在不破坏现有 Vibe2 运行前提下的并行重建进度。

**语义对齐说明**：

本文档与以下文档保持语义一致：
- `docs/plans/2026-03-13-vibe3-parallel-rebuild-design.md` - 设计真源（包含完整的命令语义定义，含第二轮补充的 handoff 写入命令）
- `docs/plans/2026-03-13-vibe3-parallel-rebuild-plan.md` - 设计冻结计划
- `docs/standards/v3/handoff-store-standard.md` - 本地 handoff store 标准（含 `handoff_items` 表）

**语义审核结果**：详见 [docs/reviews/2026-03-14-v3-semantic-alignment-review.md](../../reviews/2026-03-14-v3-semantic-alignment-review.md) - 包含完整的语义对齐检查、冲突解释和两轮修复记录。

**新增"修正与撤销"命令集**（见设计文档 "修正与撤销" 章节）：

为提升 MVP 容错率，已在设计中补齐以下命令：
- `task unlink / update`：解除链接和修正任务状态/分组
- `flow unbind task / flow unbind --issue / flow abort`：解除绑定和废弃 flow
- `pr close`：感知 PR 关闭，触发状态回退

这些命令将在 02-04 阶段逐步实现，详见各编号文档。

**新增"Handoff 基于文件编辑"语义**（见设计文档 "Handoff Identity And Authorship" 章节）：

为简化交互并符合 agent 工作方式，handoff 采用基于文件的编辑架构：
- **查看命令**：`vibe handoff plan/report/audit` - 只读不写
- **身份登记**：`vibe handoff auth plan/report/audit --agent <agent> --model <model>` - 注册身份
- **编辑命令**：`vibe handoff edit plan/report/audit` - 打开 JSON 文件进行编辑
  - **文件位置**：`.agent/handoff/{branch-safe-name}/plan.json`
  - **自动同步**：保存后系统自动解析 JSON 并同步到 SQLite 数据库
  - **自动署名**：新增记录自动从当前注册身份读取 `agent/model`
  - **自动编号**：每个 handoff type 内从 1 开始递增，删除后不回收编号
  - **内容开放**：没有权限控制，全靠 agent 自觉遵守
  - **软性约束**：通过署名机制 + 审计日志建立，而不是硬性权限控制
- **编辑方式**：
  - 添加新记录：在 `items` 数组末尾添加对象（只填 `content` 字段）
  - 修改记录：直接修改对应记录的 `content` 字段
  - 删除记录：从 `items` 数组中移除对应的对象
  - 批量删除：移除多个对象，或清空 `items` 数组

这些语义将在 01-02 阶段实现，详见 [01-command-and-skeleton.md](01-command-and-skeleton.md)。

## 当前状态

当前现场已经完成一轮错误实现线的回滚清理。

这意味着：

- `docs/v3/plans/01-04` 仍然是顺序执行真源
- 但上一轮执行 agent 写入的“已收口 / 已验证”结论不再自动成立
- 下一轮执行必须从干净现场重新跑，并重新提交验证证据

当前判断：

- 代码战场已基本清理
- 文档真源已保留
- 准备进入第二次执行尝试
- 但第二轮执行暴露出一个新问题：`v3` 又复制了 `v2` 的本地 JSON 心智，数据结构需要先重新冻结

## 核心原则

- **并行共存**：`lib/` (v2) 与 `lib3/` (v3) 物理隔离
- **三点入口**：`vibe` (默认仍保持安全入口), `vibe3` (新), `vibe2` (旧)
- **真源回归**：去本地化，回归 GitHub Issue / PR / Project 作为真源
- **责任链落地**：本地只保留 flow-scoped handoff store，不再复制业务 registry/cache
- **中子协议**：Shell 处理 CLI 与环境，Python 处理结构化逻辑与状态

## 本轮角色分工

- `planner`：负责语义冻结、`spec_ref`、现场环境准备，并确保当前 flow 已有可执行的 playbook，再以 `pr draft` 作为 planning 收尾动作
- `executor`：负责按冻结边界和当前 playbook 实现；可以补写或维护 playbook，但不擅自扩面或回写设计冻结结论
- `reviewer`：负责复杂实现审查、验证证据审查、提交前把关

推荐开场顺序是先执行对应阶段的 `vibe handoff`，再进入对应阶段。第一阶段先做责任链留痕与提示，不把未实现的物理封锁写成既成事实。

补充署名规则：

- `vibe handoff plan|report|audit` 推荐显式携带 `--agent <agent> --model <model>`
- 推荐展示形态为 `agent/model`，例如 `codex/gpt-5.4`
- 后续 handoff、audit、PR metadata 与 reviewer 结论，优先沿用这个完整署名，而不是只写 agent 名称
- `.agent/context/task.md` 在 3.0 中只作为 2.x legacy local handoff，不再承接主责任链

## 实践定位

这套 `v3` 文档已经不只是一次方案草稿，而是一次接近工程级的 Vibe Coding 实践样板。

它当前已经具备：

- 明确的角色分工
- 显式的阶段门与交接门
- 清晰的远端真源链路
- 明确的失败回退路径

后续实现应把这套文档视为执行样板，而不是自由发挥的灵感来源。

这里的 `playbook` 指 executor 可维护的施工顺序与 gate 文档，不等于 design freeze。
executor 可以写 playbook，但不能借 playbook 修改 `docs/plans/` 中已经冻结的语义、主链和边界。

## Artifact Chain

`v3` 的交接物不应只停留在 `plan`。建议把整条链固定为：

- `plan`
  - planner -> executor 的交接物
  - 负责范围、风险、执行顺序、`spec_ref`
- `report`
  - executor -> reviewer 的交接物
  - 负责实际改动、验证证据、剩余风险、阻塞点
- `audit`
  - reviewer -> ready/merge 的交接物
  - 负责审查结论、失败点、准入判断、回退建议

推荐主链理解为：

`repo issue -> task issue -> flow -> plan/spec ready -> pr draft -> report -> audit -> ready/merge`

其中：

- `pr draft` 是 planner 收尾动作
- `report` 是 execute 阶段完成后的显式交接
- `audit` 是 review 阶段完成后的显式交接

若需要本地结构化索引，也只能保存责任链最小字段，例如：

- `planner`
- `executor`
- `reviewer`
- `plan ref`
- `report ref`
- `audit ref`
- `blocked by`
- `next`

它不能扩写成 GitHub Project / issue / PR 的本地镜像。

补充要求：

- `vibe check` 必须回归 3.0 主链
- `vibe check` 负责核对本地 handoff store 与远端真源是否一致
  - **远端真源**：GitHub Project Items, GitHub Issues, GitHub PRs（通过 `gh` CLI 访问）
  - **本地记录**：SQLite handoff store（执行记录、规范、署名、追责）
  - **不缓存**：任何 GitHub 数据都不缓存到本地
- 第二轮执行前，应先完成 `v3 data model` 冻结
- 本地 handoff store 的正式结构以 `SQLite + vibe3-handoff-store-standard` 为准，执行器不得自行发明 JSON schema
- 远端 GitHub 调用必须遵守 `github-remote-call-standard`，执行器不得自行猜测 CLI / GraphQL 边界

目录边界建议同时固定为：

- `docs/plans/`
  - 放 repo 级、跨任务、跨 flow 的设计冻结与治理方案
- `docs/tasks/<task-id>/`
  - 放单条 task/flow 的 `plan / report / audit` 等长期交接物
- `docs/v3/`
  - 继续只作为这次重建的编号实施 playbook

## Gate Checklist

### Planner Ready Gate

只有当以下条件同时满足，planner 才可以执行 `pr draft` 并把现场交给 executor：

- 当前 `flow` 已建立并绑定唯一 `task issue`
- 必要的 `repo issues` 已链接清楚
- `spec_ref` 已明确
- 当前 flow 已有可执行的 playbook，且已明确到当前编号
- 当前阶段的范围、不做什么、主要风险都已写明
- 当前现场是否存在 blocked / freeze 已写明
- `plan ref` 已可见
- `planner` 署名已通过 `vibe handoff plan --agent <agent> --model <model>` 留痕
- task 范围已被合理拆分到“单个 executor 可完成”的粒度；若明显过大，应先由 planner 拆分为更小的 task / sub issue

### Executor Start Gate

executor 只有在以下条件满足时才应该开工：

- planner 已完成 `pr draft`
- `flow / branch / task issue / repo issues / spec_ref` 链路可见
- 当前要执行的 playbook / 编号文档已经明确
- 当前阶段的“建议交付物”“验证证据”“禁止扩面”都已存在
- `report` 对应的 executor 署名已准备好通过 `vibe handoff report` 写入

若上述条件不满足，executor 不应自行补规划，而应回退给 planner。

### Executor Scope Challenge

executor 在执行阶段如果判断当前 task 过大、范围混杂、无法在一次实现中安全完成，可以显式提出异议并退回给人类 / planner。

允许的动作：

- 明确指出“为什么当前 task 过大”
- 说明建议按什么维度拆分
- 建议拆成哪些 sub issue / 子 task
- 在 `report` 或 handoff 中记录当前阻塞原因

不允许的动作：

- executor 自行重写任务边界并直接扩面实现
- executor 在未拆分前，把多个本应独立的子问题揉成一次提交

默认处理方式：

- executor 提出 scope challenge
- 人类或 planner 评估后决定是否拆分为 sub issue
- 如需拆分，先更新 task/issue 结构，再重新进入执行

### Executor Report Gate

executor 在移交 reviewer 前，至少应补齐：

- `report ref`
- 实际修改路径摘要
- 已执行验证及结果
- 未解决风险 / 后续注意事项
- 当前是否仍存在 blocked / freeze
- `executor` 的 `agent/model` 署名
- 若因 task 过大而中止执行，必须明确记录 scope challenge 与建议拆分方案

没有 `report`，review 不应开始。

### Reviewer Accept / Reject Gate

reviewer 审核时至少检查：

- 实现是否仍在当前编号文档范围内
- 真实接线路径和测试/证据是否一致
- 命令输出、错误提示、非交互确认规则是否被满足
- 新增语义是否和 PRD / standards / `docs/v3` 保持一致
- 是否存在“提前切默认入口”“双实现并存”“测试测的不是实际接线代码”这类阶段性硬错误
- `report` 是否完整且和实际改动一致
- `audit ref` 是否明确记录审查结论
- `reviewer` 的 `agent/model` 署名是否留痕

只有当范围、接线、证据三者一致时，reviewer 才能给出通过结论。

## 走样与回退协议

### Executor 走样

若 executor 出现以下任一情况，默认视为走样：

- 擅自扩写规划对象或命令语义
- 跳过当前编号直接进入下一阶段
- 提前切换默认入口
- 引入第二套接线实现但未清理旧路径
- 提交“已完成/已收口”但没有验证证据

处理规则：

- 不在脏现场上继续补丁式修正
- 先由 reviewer 标记偏差点
- 必要时回退该轮实现提交
- 回到最近一个仍可信的文档 gate 重新执行

### Reviewer 审核失败

若 reviewer 判定失败，不直接进入下一编号，也不允许口头带过。必须明确给出：

- 失败类型：语义偏差 / 接线不一致 / 验证不足 / 越阶段执行
- 失败证据：文件、命令、输出或缺失项
- 回退点：回到 planner 还是回到 executor
- 重跑入口：下一次应从哪个编号、哪个 gate 重新开始
- 若审查已完成但不允许进入提交，仍应留下 `audit`，明确 reject 理由

### 回退优先级

回退时遵循以下优先级：

- 先保文档真源
- 再保单一路径接线
- 最后才恢复实现推进

若实现与文档冲突，优先回到文档 gate；若测试与接线冲突，优先停下清理战场，而不是继续堆测试。

## `flow show` 需要看到什么

后续 `flow show` / `flow status` 至少应能看到这些 ref，避免多 flow 并行时重新翻目录：

- `spec ref`
- `plan ref`
- `report ref`
- `audit ref`
- `planner`
- `executor`
- `reviewer`
- `task issue`
- `repo issues`
- `branch`
- `pr`

## 进度看板

- [x] **01. Command And Skeleton** - [已完成](01-command-and-skeleton.md)
  - 骨架建立，输出/错误锚定，Python 入口定型。
- [ ] **02. Flow Task Foundation** - [待执行](02-flow-task-foundation.md)
  - 打通 `repo issue -> task issue -> flow(branch)` 链路。
- [ ] **03. PR Domain** - [待执行](03-pr-domain.md)
  - 交付链独立，支持 Draft、Ready、Review、Merge 分段管理。
- [ ] **04. Handoff And Cutover** - [待执行](04-handoff-and-cutover.md)
  - 备忘录自动同步，是否切换默认入口需要二次验证后再决定。
- [ ] **05. Polish And Cleanup** - [待执行](05-polish-and-cleanup.md)
  - 归档旧代码，优化性能，补齐文档与上手教程。

## 如何验证

1. 运行 `bin/vibe` 或 `bin/vibe3` 确认未提前切换到 `v3`
2. 检查 `git log` 确认冲突实现已撤销
3. 下一轮执行后，重新补 `tests3/` 的有效验证证据

## 如何回退

如果 Vibe3 工作不符合预期，请使用 `vibe2` 显式调用旧逻辑。

---
Current State: **Battlefield Cleaned, Execution Reset**. Ready for a second execution attempt after reverting conflicting implementations.
