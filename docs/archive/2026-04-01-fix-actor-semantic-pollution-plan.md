# Fix: actor 语义污染 — orchestra 抢占 actor 字段

- **Issue**: #411
- **优先级**: P1 (bug — 概念模型被破坏)
- **分支**: 基于 main 新建 `fix/actor-semantic-pollution`
- **预估改动**: ~8 文件，~80 行

## 背景

`actor` 的原始设计语义是 "哪个 AI agent 或 human 在操作"（格式 `backend/model`），但 orchestra 组件把自身标识（`"orchestra"`）写入了 `latest_actor` 字段，导致 `vibe3 flow show` 显示混乱的非 agent 身份。

核心矛盾：actor 回答"谁在做事"，orchestra 回答"什么组件发起了 flow"。这是两个不同维度，不能共用同一字段。

## 修复方案

引入 `initiated_by` 字段标识 flow 发起源，同时让 `actor` 守住 agent/human 身份语义。

## Task List

### Phase 1: 模型层 (无破坏性)

- [ ] **T1.1** `src/vibe3/models/flow.py`
  - FlowState 新增 `initiated_by: str | None = None`
  - 放在 `latest_actor` 之后

- [ ] **T1.2** `src/vibe3/clients/sqlite_client.py`
  - `VALID_FLOW_STATE_FIELDS` 增加 `"initiated_by"`

### Phase 2: 服务层

- [ ] **T2.1** `src/vibe3/services/flow_service.py`
  - `create_flow()` 增加可选参数 `initiated_by: str | None = None`
  - 传递到 `store.update_flow_state(branch, ..., initiated_by=initiated_by)`

### Phase 3: Orchestra 修正 (核心改动)

- [ ] **T3.1** `src/vibe3/orchestra/flow_orchestrator.py`
  - `create_flow_for_issue()` 中：
    - `actor="orchestra"` 改为 `actor=None`（此时无 agent 接手）
    - 新增 `initiated_by="orchestra:dispatcher"`
  - `task_service.link_issue()` 中：
    - `actor="orchestra"` 改为 `actor=None`
  - 方法签名保持不变（不向调用方暴露 `initiated_by` 参数，内部硬编码即可）

### Phase 4: UI 展示

- [ ] **T4.1** `src/vibe3/ui/flow_ui.py`
  - `_render_flow_state()` 中：在 `actor` 行之前增加 `initiated_by` 展示
  - `_render_flow_status()` 紧凑摘要行也展示 `initiated_by`（仅当非 None）

### Phase 5: 文档

- [ ] **T5.1** `docs/standards/glossary.md`
  - §7 Identity Tracking Terms 新增：
    - `7.3 actor` — 执行操作的 Agent 或 Human 身份标识
    - `7.4 initiated_by` — flow 的发起源标识（orchestra:dispatcher / manual / skill:vibe-new）

### Phase 6: 测试

- [ ] **T6.1** `tests/vibe3/orchestra/test_flow_orchestrator.py`
  - 更新 `create_flow_for_issue` 测试，断言 `actor` 不再是 `"orchestra"`
  - 断言 `initiated_by` 被正确设置

- [ ] **T6.2** 新增或更新 `tests/vibe3/services/test_flow_service.py`
  - 测试 `create_flow(initiated_by=...)` 参数传递

## 不改动的部分

以下使用合理，**不需要修改**：

- **LabelService** 中 `actor="orchestra:triage"` / `"orchestra:manager"` / `"orchestra:dispatcher"`
  — 这些是 event/transition 级的 actor，标识"谁触发了这个 label 变更"，与 flow state 的 `latest_actor` 无关
- **Event 系统** (`store.add_event()`) 中的 actor 参数
  — 事件是审计日志，允许记录系统组件来源
- **result_handler.py** 和 **master_handler.py** 中的 label actor
  — 不影响 flow state

## 迁移说明

- `initiated_by` 是新增字段，默认 `None`，对已有 flow 零破坏
- 旧 flow 的 `latest_actor` 如果是 `"orchestra"`，不做数据迁移（历史数据保留原样）
- SQLite 是 schema-less 的 JSON 存储，无需 migration

## 验证步骤

1. `uv run pytest tests/vibe3/orchestra/test_flow_orchestrator.py -v`
2. `uv run pytest tests/vibe3/services/ -v`
3. `uv run mypy src/vibe3/`
4. 手动验证 `vibe3 flow show` 输出格式
