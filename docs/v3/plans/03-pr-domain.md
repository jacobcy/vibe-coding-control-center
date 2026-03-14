# 03. PR Domain

目标：把 `pr` 域独立出来，补齐交付链，而不是继续把 PR 逻辑藏在 flow 里。

## 必读输入

- `docs/plans/2026-03-13-vibe3-parallel-rebuild-design.md`
- `docs/v3/02-flow-task-foundation.md`
- `docs/plans/2026-03-12-changelog-msg-cache-plan.md`
- `docs/plans/2026-03-11-commit-preflight-metadata-plan.md`
- `docs/standards/git-workflow-standard.md`

## 当前上下文

这一阶段负责把“看得见的执行主链”延伸到“看得见的交付主链”。

用户的核心痛点是：多条 flow 并行时，如果没有 draft PR，链路会散；但如果 PR 逻辑做得过重，又会把版本号、changelog、review、merge 顺序搅在一起。

这里还要锁定一个流程修正：`pr draft` 不是 planning 前的动作，而是 planner 在 plan/spec/现场准备完成后的收尾动作。

所以这一轮必须把 `pr` 拆成清晰阶段：

- `pr draft`
- `pr report`
- `pr audit`
- `pr review`
- `pr ready`
- `pr merge`

这一轮只做这些事：

- `pr draft`
- `pr show`
- `pr review`
- `pr ready`
- `pr merge`

**修正与撤销命令（本阶段可暂缓实现）**：

以下命令已在设计文档中定义（见 `docs/plans/2026-03-13-vibe3-parallel-rebuild-design.md` "修正与撤销" 章节），用于错误恢复：

- `pr close`：本地感知 PR 关闭，触发 Task 状态回退（从 `in_progress` 回到 `todo`）

这个命令虽然属于 PR 域，但可以在后续阶段实现。当 PR 在 GitHub 上被关闭（非 merged）时，需要感知并清理本地状态。

这一轮重点：

- `pr draft` 绑定：
  - `task issue`
  - `repo issues`
  - `spec_ref`
  - `agent`
  - 且只在 planning ready 后执行
- `pr review` 支持本地 Codex 审查，并把结论回贴到 PR
- `pr ready` 进入 publish gate
- group 驱动默认 bump 策略：
  - `feature` 默认走 bump/changelog
  - `bug/docs/chore` 默认不 bump，除非显式传参

## 真源与边界

- draft PR 是远端可见锚点
- draft PR 的创建时机属于 planner 收尾，而不是 planning 前置
- `spec_ref` 必须进入 PR 链路
- `task issue` / `repo issues` 必须进入 PR 链路
- 版本 bump / changelog 是 publish gate 行为，不是 draft 行为
- review 结果不能只停在本地，必须能回贴 PR

## 默认行为必须锁定

- `pr draft`
  - planner 在 planning ready 后建 draft PR
  - 绑定 `task issue` / `repo issues` / `spec_ref` / `agent`
  - 默认不 bump
- `pr review`
  - 可用本地 Codex 审查
  - 输出结构化 review
  - 支持回贴 PR comment 或回复 review thread
- `pr ready`
  - 跑 metadata preflight
  - **检查 `report` 和 `audit` 是否在当前 flow 的责任链中已准备就绪**
  - `feature` 默认进入 bump/changelog 逻辑
  - `bug/docs/chore` 默认不 bump，除非显式参数
- `pr merge`
  - merge 后推动 task 状态收口

## 建议交付物

- `pr draft`
- `pr show`
- `pr review`
- `pr ready`
- `pr merge`
- `tests3/pr/`
- `tests3/contracts/`

## 验证证据 (历史记录，当前已失效)

以下证据来自上一轮失败执行，在战场清理后不再视为当前有效证据：

```text
 ✓ vibe3 pr draft creates PR and binds task
 ✓ vibe3 pr ready and merge
 ✓ feature group defaults to bump
 ✓ bug group defaults to no-bump
 ✓ explicit --bump overrides default policy
```

主要逻辑点验证：
- `pr draft` 自动注入 Metadata (Task ID, Group, Flow) 到 PR Description
- `pr ready` 按 `group` 正确区分 `Bump=True/False`
- `pr merge` 成功后，Registry 中的 Task 状态变为 `completed`

## 当前状态（清理后）

- `03` 的目标和边界仍有效
- 上一轮“已收口”结论已失效
- 下一轮执行必须重新提交：
  - `pr draft/review/ready/merge` 的真实接线证据
  - `group -> bump` 策略证据
  - `spec_ref` 与 review comment 回贴证据

状态：**待二次执行**。不得直接跳到 `04`，除非重新验证通过。

## 进入下一轮的条件

只有当 `planner ready -> draft -> review -> ready -> merge` 这条交付链具备清晰证据，才能进入 `04`。

建议动到的文件：

- `lib3/pr/`
- `scripts/python/v3/pr/`
- `tests3/pr/`
- `tests3/contracts/`

收口标准：

- draft PR 建立后，链路可见
- review 结论可落到 PR
- ready 阶段能按 group 和参数正确决定是否 bump
- merge 后 task 状态能收口

做完以后再进入 `04`。
