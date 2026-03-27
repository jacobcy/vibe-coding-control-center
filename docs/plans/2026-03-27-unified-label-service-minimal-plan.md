# Unified Label Service 最小改造计划（Issue/PR 状态确认）

**日期**: 2026-03-27  
**状态**: Draft（待实现）  
**目标**: 状态变更统一调用标签服务；标签服务通过接口完成 issue / pr 事实确认与最小推进。

---

## 1. 背景问题

当前状态变更链路分散：

1. `plan/run/review` 通过 `label_integration.py` 调 `LabelService`
2. `flow blocked/done` 未统一进入标签状态确认链路
3. `pr ready` 只做 PR 状态同步，本轮目标未统一回写 issue `state/merge-ready`
4. `TaskLabelService` 与 `LabelService` 都直接调用 `gh`，存在重复实现

结果：状态确认逻辑分散、幂等策略不一致、难以统一“先确认事实，再最小动作”。

---

## 2. 目标与非目标

## 2.1 目标

1. 建立统一入口：所有状态变更由 `LabelService` 触发。
2. `LabelService` 通过接口（port）确认事实，不在上层命令散落 GitHub 调用。
3. 对外统一返回三态结果：`confirmed` / `advanced` / `blocked`。
4. 覆盖命令：`plan/run/review/flow blocked/pr ready/flow done`。

## 2.2 非目标

1. 不重写整个 `GitHubClient`。
2. 不修改命令参数语义。
3. 不在本轮引入新的状态集合（仍使用 `state/*` + `vibe-task`）。

---

## 3. 设计方案（最小）

## 3.1 统一服务职责

在 `src/vibe3/services/label_service.py` 内聚两类能力：

1. `state/*` 状态迁移（已有）
2. `vibe-task` 镜像（从 `TaskLabelService` 合并而来）

并新增“确认式 API”：

1. `confirm_issue_state(issue_number, target_state, actor) -> confirmed|advanced|blocked`
2. `confirm_vibe_task(issue_number, should_exist) -> confirmed|advanced|blocked`

说明：
- `confirmed`: 远端事实已满足，仅同步/返回
- `advanced`: 做了最小推进动作（例如补标签、迁移状态）
- `blocked`: 无法满足条件且不可推进

## 3.2 接口（port）抽象

新增 `src/vibe3/services/state_sync_ports.py`（名称可微调）：

1. `IssueStatePort`
   - `get_issue_labels(issue_number)`
   - `add_issue_label(issue_number, label)`
   - `remove_issue_label(issue_number, label)`
2. `PrStatePort`
   - `get_pr(pr_number=None, branch=None)`
   - `mark_ready(pr_number)`
   - `merge_pr(pr_number)`（供 `flow done` 后续复用）

默认实现先复用 `GitHubClient`，不新增 CLI 命令层逻辑。

## 3.3 命令侧调用统一

1. `plan/run/review`: 不再直接依赖 `label_integration`，改调 `LabelService.confirm_issue_state(...)`
2. `pr ready`:
   - 先确认 PR ready 事实
   - 再同步关联 task issue 为 `state/merge-ready`（若存在）
3. `flow blocked`:
   - flow 本地状态改为 blocked 后
   - 统一调用 `LabelService.confirm_issue_state(task_issue, state/blocked, ...)`
4. `flow done`:
   - 先确认 PR 是否 merged（已 merged -> confirmed）
   - 可 merge 则 merge（advanced）
   - 关闭后将 flow 下全部 `role=task` issue 置为 `state/done`

---

## 4. 实施步骤（按最小风险顺序）

1. 抽接口 + 适配层（不改命令行为）
2. 合并 `TaskLabelService` 到 `LabelService`，保留兼容包装
3. 替换 `label_integration` 调用点（plan/run/review）
4. 接入 `pr ready` 与 `flow blocked/done` 的统一确认调用
5. 删除重复逻辑（`TaskLabelService` 内部实现、`label_integration` 冗余函数）

---

## 5. 测试计划

新增/调整测试：

1. `tests/vibe3/services/test_label_service.py`
   - `confirm_issue_state` 的 confirmed/advanced/blocked
   - `confirm_vibe_task` 的 add/remove 幂等
2. 更新 `tests/vibe3/services/test_label_integration.py`
   - 若保留兼容层，仅测转发
3. 扩展
   - `tests/vibe3/services/test_pr_ready_usecase.py`
   - `tests/vibe3/services/test_flow_lifecycle.py`
   - `tests/vibe3/services/test_task_label_service.py`（若被替换则迁移/删除）

---

## 6. 验收标准

1. 状态变更命令统一走 `LabelService`，无命令层直连标签操作。
2. issue 状态迁移与 `vibe-task` 镜像都具备幂等确认行为。
3. `pr ready` 与 `flow done` 能体现“先确认事实，再最小推进”。
4. 测试覆盖通过，且不引入新的状态语义分叉。
