---
document_type: plan
title: Flow Events → Narrative Timeline + Handoff Chain Framework
status: draft
author: Claude (Sisyphus)
created: 2026-03-23
last_updated: 2026-03-23
related_docs:
  - src/vibe3/clients/sqlite_client.py
  - src/vibe3/services/flow_service.py
  - src/vibe3/services/pr_service.py
  - src/vibe3/services/task_service.py
  - src/vibe3/commands/review.py
  - src/vibe3/ui/flow_ui.py
  - docs/standards/v3/handoff-store-standard.md
---

# Flow Events → Narrative Timeline + Handoff Chain Framework

## 核心思路

不做新表，不碰 vibe-save。增强现有 `flow_events`，让所有写命令都产出 event，flow show 读 event 渲染时间线。

handoff 就是 agent 链：`spec_ref → plan_ref → report_ref → audit_ref`，已经在 `flow_state` 表里，框架搭好后 plan/run 直接接上。

---

## 现状

### 已有：写入 event 的命令

| 命令 | event_type | 文件 |
|------|-----------|------|
| flow new | `flow_created` | flow_service.py:91 |
| flow bind | `task_bound` | flow_service.py:143 |
| task link | `issue_linked` | task_service.py:61 |
| task status | `status_updated` | task_service.py:111 |
| task next | `next_step_set` | task_service.py:178 |
| pr draft | `pr_created` | pr_service.py:99 |
| pr ready | `pr_ready` | pr_service.py:164 |
| pr merge | `pr_merged` | pr_service.py:208 |

### 缺失

| 问题 | 影响 |
|------|------|
| `flow_events` 无 `get_events()` | 只能写不能读 |
| `flow_events` 无 `refs` 列 | 无法关联文件附件 |
| review 不写 event，不设 `audit_ref` | review 产出不进入 flow 链 |
| `flow show` 渲染静态快照 | 不显示事件历史 |
| plan / run 未实现 | 需要预留框架 |

---

## 实现

### Phase 1: flow_events 增强

**文件**：`src/vibe3/clients/sqlite_client.py`

```sql
-- 加 refs 列（向后兼容，旧数据不受影响）
ALTER TABLE flow_events ADD COLUMN refs TEXT;  -- JSON: {"files": [...], "ref": "..."}
```

新增方法：

```python
def get_events(
    self, branch: str, event_type: str | None = None,
    limit: int = 50, offset: int = 0,
) -> list[dict[str, Any]]:
    """Get events for branch, ordered by created_at DESC."""

def add_event(
    self, branch: str, event_type: str, actor: str,
    detail: str | None = None, refs: dict[str, Any] | None = None,  # 新增
) -> None:
    """Add event with optional refs."""
```

**验收**：
- [ ] `refs` 列正确添加
- [ ] `get_events()` 返回事件列表，支持按 event_type 过滤
- [ ] `add_event()` 支持 `refs` 参数

---

### Phase 2: review 产出 event + audit_ref

**文件**：`src/vibe3/commands/review.py`

review 完成后：
1. 写 event：`event_type="handoff_review"`, `detail=review 摘要`, `refs={"audit_ref": "path/to/review.md"}`
2. 设 `audit_ref` 到 `flow_state`

```python
# review.py pr() 函数，review 完成后
store = SQLiteClient()
branch = GitClient().get_current_branch()
store.add_event(
    branch, "handoff_review", actor="codex/gpt-5.4",
    detail=f"Review verdict: {review.verdict}, {len(review.comments)} comments",
    refs={"audit_ref": review_output_path, "pr_number": pr_number},
)
store.update_flow_state(
    branch, audit_ref=review_output_path,
    reviewer_actor="codex/gpt-5.4",
)
```

**验收**：
- [ ] `review pr` 完成后写入 `handoff_review` event
- [ ] `flow_state.audit_ref` 被设置
- [ ] event 的 `refs` 包含 review 输出路径

---

### Phase 3: flow show → 时间线叙事

**文件**：
- `src/vibe3/services/flow_service.py` — 新增 `get_flow_timeline()`
- `src/vibe3/ui/flow_ui.py` — 新增 `render_flow_timeline()`
- `src/vibe3/commands/flow.py` — `show()` 默认走叙事

#### FlowService.get_flow_timeline()

```python
def get_flow_timeline(self, branch: str) -> dict:
    state = self.store.get_flow_state(branch)
    events = self.store.get_events(branch, limit=100)
    return {"state": state, "events": events}
```

#### render_flow_timeline()

```
$ vibe flow show feature-handoff

📋 Flow: feature-handoff
   Branch: task/feature-handoff
   Status: active
   Issue: #121

═══ Timeline ═══

2026-03-20 10:00  [claude] flow_created
  Flow 'feature-handoff' created from #121

2026-03-21 14:30  [claude] pr_created
  Draft PR #169 created
  📎 docs/plans/2026-03-23-handoff-append-narrative-plan.md

2026-03-21 16:00  [codex/gpt-5.4] handoff_review
  Review verdict: APPROVE, 3 comments
  📎 docs/v3/reviews/pr-169-review.md

═══ Current ═══
  spec_ref:   docs/specs/feature-handoff.md
  plan_ref:   (pending)
  report_ref: (pending)
  audit_ref:  docs/v3/reviews/pr-169-review.md
  Next:       实现 render_flow_timeline()
```

#### show 命令

```python
@app.command()
def show(
    flow_name: str | None = None,
    snapshot: bool = False,  # --snapshot 回退到旧静态显示
    json_output: bool = False,
):
    if snapshot:
        render_flow_status(flow_status)  # 旧逻辑
    else:
        timeline = service.get_flow_timeline(branch)
        render_flow_timeline(timeline)  # 新逻辑
```

**验收**：
- [ ] `flow show` 默认显示时间线叙事
- [ ] `flow show --snapshot` 回退静态快照
- [ ] `flow show --json` 输出结构化 timeline
- [ ] 底部显示 Current 区域（refs + next_step）

---

### Phase 4: handoff show 命令

**文件**：
- `src/vibe3/commands/handoff.py` — 新建

`handoff show` 是 `flow show` 的过滤视图 — 只显示 agent 链上的事件：

```
$ vibe handoff show

📋 Handoff: feature-handoff

═══ Agent Chain ═══

spec_ref:    docs/specs/feature-handoff.md  [claude]
plan_ref:    (pending)
report_ref:  (pending)
audit_ref:   docs/v3/reviews/pr-169-review.md  [codex/gpt-5.4]

═══ Recent Handoff Events ═══

[2026-03-21 16:00] codex/gpt-5.4 · handoff_review
Review verdict: APPROVE, 3 comments

建议：
- flow_events 需要 get_events()
- review 应产出 event

📎 refs:
  - docs/v3/reviews/pr-169-review.md
```

**实现要点**：
- 读 `flow_events`，过滤 `event_type LIKE 'handoff_%'`
- 读 `flow_state` 的 ref 字段显示 agent 链
- 默认显示最近 5 条，`--all` 显示全部

**验收**：
- [ ] `handoff show` 显示 agent 链 + 最近 handoff 事件
- [ ] `handoff show --all` 显示完整历史

---

### Phase 5: 未来扩展预留

plan / run 命令实现时，只需：

```python
# plan 命令完成时
store.add_event(branch, "handoff_plan", actor, detail="...", refs={"plan_ref": path})
store.update_flow_state(branch, plan_ref=path, planner_actor=actor)

# run 命令完成时
store.add_event(branch, "handoff_run", actor, detail="...", refs={"report_ref": path})
store.update_flow_state(branch, report_ref=path, executor_actor=actor)
```

和 review 走同一条路，不需要额外改动。

---

## 不动的

| 组件 | 理由 |
|------|------|
| `flow_state` 表 | ref 字段已存在，不用改 |
| `flow_issue_links` 表 | issue 关联，不动 |
| `vibe-save` skill | 人类视角，不在本次范围 |
| V2 `flow_show.sh` | 读 worktrees.json，不影响 |

---

## 时间估算

| Phase | 交付 | 时间 |
|-------|------|------|
| 1: flow_events 增强 | refs 列 + get_events() | 1h |
| 2: review 产出 event | review.py 改造 | 1h |
| 3: flow show 叙事 | 时间线渲染 | 2h |
| 4: handoff show | agent 链视图 | 1h |
| 5: 测试 | 单元 + 集成 | 1h |
| **总计** | | **6h** |
