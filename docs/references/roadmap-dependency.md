# Roadmap Dependency Reference

本文档记录 `roadmap item` 依赖关系的草案设计与术语候选，用于评审、实现对照与后续标准化准备。

它是参考材料，不是当前标准真源。

当前有效真源仍以：

- `docs/standards/v2/data-model-standard.md`
- `docs/standards/v2/roadmap-json-standard.md`
- `docs/standards/v2/command-standard.md`

为准。

## 讨论目标

- roadmap item 的依赖关系应建模在哪一层
- `ready` / `blocked` / `blockers` 应如何解释
- 依赖声明需要满足哪些最小校验规则
- 依赖语义与 task / flow / GitHub Project sync 的边界如何分离

## 草案要点

### 1. Layer

- 依赖关系只在 `roadmap item` 层建模
- `task` 继续负责 execution record
- `flow` 继续负责 runtime 容器
- 不把 branch、worktree、PR 本体当作依赖对象

### 2. Field

候选字段：

- `depends_on_item_ids`

候选约束：

- 字段落点在 `roadmap.json.items[]`
- 类型是字符串数组
- 不允许 `null`
- 不允许重复 ID
- 不允许自依赖

### 3. Computed View

候选派生视图：

- `ready`
- `blocked`
- `blockers`

讨论口径：

- `ready/blocked` 是查询结果，不持久化为共享真源
- `blockers` 只列当前仍未解除阻塞的前置项

### 4. Evidence

当前草案倾向：

- 解除依赖的强证据应来自依赖项对应主 PR 已 merged
- 单纯的 task `completed`、roadmap 本地状态或 handoff 文案都不足以解除依赖

这仍是参考口径，不代表仓库当前已批准的标准语义。

### 5. Validation

候选校验规则：

- 引用项必须存在
- 不允许自依赖
- 不允许重复依赖
- 不允许形成环
- 不允许写入 task_id / branch / worktree_name / pr_ref / repo issue ref

### 6. Query Surface

可能的查询暴露面：

- `roadmap list`
- `roadmap show`
- `roadmap status`

讨论目标：

- 暴露 `depends_on_item_ids`
- 暴露 `blockers`
- 允许输出 `missing_pr_ref` / `pr_not_merged` 这类缺失证据原因

### 7. Future Work

若后续要把这份参考材料升级为标准，至少还需要补齐：

- 与现行 schema 的最终对齐
- 与真实 PR 真源的一致实现路径
- gate 入口范围与阻断语义
- 参考文档到标准文档的正式迁移决议
