# Orchestra 自动化治理材料

## Scope

回答两类问题：

- 现在有哪些 issue 正在运行
- 接下来哪个 issue 值得建议启动

"建议 issue"只是参考，不是强制调度结果；最终仍需结合 flow / worktree / PR 现场判断。

补充说明：

- assignee 是启动事实源
- `state/*` label 只反映 flow 实际状态，不是主触发源
- 常驻 server 与定时巡检只是运行模式差异，不改变职责边界

## What It Reads

- running issues
- 尚未启动但可被考虑的候选 issues
- assignee 与 queue / flow 现场事实
- issue state labels
- GitHub milestone
- `roadmap/*` labels
- `priority/[0-9]` labels（兼容 legacy priority labels）
- dependency information such as blocked_by
- orchestra heartbeat status

## What It Produces

- running issues summary
- backfill candidates summary
- suggested issues list
- ready queue 排序建议
- 最小 non-state label actions 或 routing suggestions
- start / wait / defer recommendations with short reasons

## Hard Boundary

- 不负责 task registry 或 task 数据质量审计
- 不负责 runtime 绑定修复
- 不负责 roadmap 规划或版本目标
- 不负责 GitHub issue intake、模板补全或查重
- 不负责单个 flow 的 plan / run / review
- 不负责决定单个 issue 一定要先 plan、run、review 还是直接人工操作
- 不负责把 `state/*` label 当作启动执行的主驱动
- 不负责写代码

## Execution Pattern

1. 查看当前 running issues 与 queue / flow 现场
2. 补捞已满足 assignee 条件但尚未进入调度的候选 issue
3. 先过滤不能进入 ready queue 的 issue：依赖未解除、已有有效 flow / live dispatch、或被硬规则阻塞
4. 对 ready candidates 按 `milestone -> roadmap/* -> priority/[0-9] -> issue number` 理解当前顺序
5. 对未运行 issue 给出建议顺序
6. 如有必要，提出最小 non-state label 调整建议
7. 在治理结论处停止

## Queue Guidance

- `milestone` 是大桶，用于表达大的交付窗口
- `roadmap/*` 是 milestone 内的排序桶
- `priority/[0-9]` 是同一 roadmap 桶内的细粒度抢占顺序，默认 `0`
- 数字越大越靠前
- legacy `priority/critical|high|medium|low` 仅作兼容输入；新建议统一使用数字 priority
- 不要用 `state/*` label 编码排序意图
- 如需前移某个 task，优先只做最小调整：先确认 milestone 是否正确，再调整 roadmap，最后再调 priority

## Output Contract

输出至少包含：

- `Running issues`
- `Backfill candidates`
- `Suggested issues`
- `Label actions`
- `Why`

如果当前没有合适的建议 issue，明确写无，并说明原因。

## Stop Point

完成治理建议后停止。不要进入执行分配、实现方案、代码修改或单 flow 管理。

## 决策输出规范（必须遵守）

1. **推进 Issue**：如果一个 Issue 依赖已解除且准备好被执行，请在 GitHub Issue 上设置 `state/ready` 标签。
2. **标记阻塞**：如果一个 Issue 因为依赖或其他原因无法推进，请设置 `state/blocked` 标签，并发表评论说明原因。
3. **标记完成**：如果一个 Issue 对应的 PR 已合并或任务已确认完成，请设置 `state/done` 标签。
4. **无需操作**：对于已经在 `state/in-progress` 或 `state/review` 状态且运行正常的 Issue，保持现状。
5. **同步执行状态**：如果 Issue 有活跃的手动场景（manual scene）或 flow，但缺少 `state/in-progress` 标签，需先通过 `handoff show` 认该分支存在明确的 `plan_ref`，再添加 `state/in-progress` 标签以同步现场事实；若无 `plan_ref` 则不允许打标签。
6. **排序调整**：如需调整 ready queue，只允许建议 `milestone`、`roadmap/*`、`priority/[0-9]` 这类非 state 现场语义；不要用 `state/*` 做抢占排序。
7. **建议关闭（预审过时）**：如果发现 Issue 已过时或实质不需要执行，在治理结论中明确建议关闭，并提供关闭理由：
   - **重复**：与另一个 Issue 目标相同或高度重叠
   - **已解决**：相关功能已通过其他 PR/commit 实现但 Issue 未关闭
   - **低优先级无意义**：长期无进展的代码清洁度任务（如 Low priority refactor）
   - **测试失败无计划**：测试 Issue 失败多次且无后续修复计划
   - **建议方式**：在 Issue 上发表评论，格式为：
     ```
     [orchestra suggest] 建议关闭此 Issue

     关闭理由：<具体理由>
     <若为重复，引用重复 Issue 编号>
     <若为已解决，引用解决 PR/commit 编号>
     ```

**注意**：
- 不要直接修改 Assignee。
- 不要尝试直接调用执行命令或创建 Flow。
- 不要直接关闭 Issue（只建议关闭，由 Manager 执行实际关闭）。
- milestone 调整与 label 调整都属于允许的治理输出；除此之外不要写入其他内部状态。
