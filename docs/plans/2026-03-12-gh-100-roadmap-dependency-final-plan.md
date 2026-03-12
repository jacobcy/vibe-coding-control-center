---
document_type: plan
title: GH-100 Roadmap Dependency Implementation Plan (Final)
status: active
author: Claude Sonnet 4.6
created: 2026-03-12
last_updated: 2026-03-12
related_docs:
  - docs/standards/roadmap-dependency-standard.md
  - docs/standards/glossary.md
  - docs/standards/data-model-standard.md
  - docs/standards/roadmap-json-standard.md
---

# GH-100 Roadmap Dependency Implementation Plan (Final)

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 为 roadmap item 引入轻量依赖声明与 ready/blocked 视图，分两阶段实施：先做查询层，后做 flow gate（#124 已通过 PR #143 完成）。

**Architecture:**
- 依赖声明真源留在 `roadmap.json.items[].depends_on_item_ids`
- 查询层暴露 `ready/blocked/blockers` 与缺失证据类型
- **Phase 2** 才会把 gate 逻辑接到 `flow new` / `flow bind issue`（#124 的 issue->flow 主链已通过 PR #143 稳定）

**Tech Stack:** Zsh, jq, bats, GitHub CLI

---

## Phase 1: 查询层与标准固定（当前可执行）

**前置条件**:
- 无需等待其他 issue
- 不依赖 flow 主链调整
- 可独立交付价值

### Task 1.1: 固定依赖字段与标准引用

**Files:**
- Modify: `docs/standards/roadmap-json-standard.md`
- Modify: `docs/standards/data-model-standard.md`
- Reference: `docs/standards/roadmap-dependency-standard.md`

**Step 1: 写文档断言清单**

列出必须被标准化的三件事：
- `depends_on_item_ids` 是 roadmap item 字段
- merged PR 是解除依赖唯一证据
- ready/blocked 是派生视图，不持久化

**Step 2: 更新 schema 标准**

手工编辑标准文档
Expected: `roadmap-json-standard.md` 明确 `depends_on_item_ids` 字段形态与约束

**Step 3: 更新高层模型标准**

手工编辑标准文档
Expected: `data-model-standard.md` 引用依赖标准，不再各自发明 gate 语义

**Step 4: 目视核对**

```bash
rg -n "depends_on_item_ids|ready/blocked|merged PR" docs/standards
```

Expected: 三份标准的关键术语一致

---

### Task 1.2: 补查询层，算出 ready/blocked/blockers

**Files:**
- Modify: `lib/roadmap_query.sh`
- Modify: `lib/roadmap_write.sh` 或相关 roadmap item 构造路径
- Test: `tests/contracts/test_shared_state_contracts.bats`
- Test: `tests/roadmap/test_roadmap_status_render.bats`

**Step 1: 写失败测试**

目标场景：
- 一个 roadmap item 无依赖，应显示 `ready`
- 一个 roadmap item 依赖另一个未满足 merged PR 的 item，应显示 `blocked`
- blocker 输出应区分 `missing_pr_ref` 与 `pr_not_merged`

**Step 2: 跑失败测试**

```bash
bats tests/contracts/test_shared_state_contracts.bats tests/roadmap/test_roadmap_status_render.bats
```

Expected: 新增断言失败，提示尚无依赖计算字段

**Step 3: 实现最小查询能力**

实现要求：
- 允许 roadmap item 持有 `depends_on_item_ids`
- 查询时根据依赖项 bridge 计算：
  - `ready`: 所有依赖项都有 merged PR 证据
  - `blocked`: 至少一个依赖项缺失证据
  - `blockers`: 列出阻塞项及原因（`missing_pr_ref` / `pr_not_merged`）

**Step 4: 回跑测试**

```bash
bats tests/contracts/test_shared_state_contracts.bats tests/roadmap/test_roadmap_status_render.bats
```

Expected: 新增依赖查询断言通过

**Step 5: Commit**

```bash
git add docs/standards/roadmap-json-standard.md docs/standards/data-model-standard.md lib/roadmap_query.sh lib/roadmap_write.sh tests/contracts/test_shared_state_contracts.bats tests/roadmap/test_roadmap_status_render.bats
git commit -m "feat: add roadmap dependency query layer

- Add depends_on_item_ids field to roadmap item
- Implement ready/blocked/blockers computation
- Distinguish missing_pr_ref vs pr_not_merged blockers
- Update standards to reference dependency model"
```

---

### Task 1.3: 给 roadmap status/show 加 blocker 可见性

**Files:**
- Modify: `lib/roadmap_query.sh`
- Modify: `lib/roadmap_help.sh`
- Test: `tests/roadmap/test_roadmap_status_render.bats`
- Test: `tests/contracts/test_roadmap_contract.bats`

**Step 1: 写失败测试**

目标场景：
- `roadmap status` 能显示 ready/blocked 数量
- `roadmap show` 能看到 blocker 证据缺口
- help 文案提到依赖查询

**Step 2: 跑失败测试**

```bash
bats tests/roadmap/test_roadmap_status_render.bats tests/contracts/test_roadmap_contract.bats
```

Expected: 新增状态与 help 断言失败

**Step 3: 实现最小展示**

实现要求：
- 文本与 JSON 都暴露 blocker 结果
- 不把派生状态写回 roadmap 真源

**Step 4: 回跑测试**

```bash
bats tests/roadmap/test_roadmap_status_render.bats tests/contracts/test_roadmap_contract.bats
```

Expected: blocker 可见性测试通过

**Step 5: Commit**

```bash
git add lib/roadmap_query.sh lib/roadmap_help.sh tests/roadmap/test_roadmap_status_render.bats tests/contracts/test_roadmap_contract.bats
git commit -m "feat: expose roadmap blocker visibility

- Show ready/blocked counts in roadmap status
- Display blocker details in roadmap show
- Update help to mention dependency queries"
```

---

### Task 1.4: 做端到端回归与验证

**Files:**
- Test only

**Step 1: 跑核心测试集**

```bash
bats tests/contracts/test_shared_state_contracts.bats tests/roadmap/test_roadmap_status_render.bats tests/contracts/test_roadmap_contract.bats
```

Expected: 全部通过

**Step 2: 手工核对关键命令**

```bash
bin/vibe roadmap status --json
bin/vibe roadmap show <item-id> --json
```

Expected:
- blocker 信息可见
- ready/blocked 计算正确

**Step 3: Commit**

```bash
git commit --allow-empty -m "test: verify roadmap dependency query layer end-to-end"
```

---

## Phase 2: Flow Gate 集成（#124 已完成）

**前置条件**:
- ✅ **#124 已完成**: issue->flow 主链已通过 PR #143 稳定
- ✅ flow identity / flow bind issue 语义已收敛
- ✅ 可以安全地添加 gate 逻辑

**Scope:**
- 补 flow 层，issue -> roadmap item 解析与依赖门禁
- 做双入口门禁（flow new + flow bind issue）
- **不提供跳过 gate 的软开关**

**详细实施步骤**: 可基于当前 flow 主链设计开始规划

---

## Risks

- **#119** 当前仍存在 runtime metadata 缺口，若 gate 需要稳定读取 `pr_ref` / branch bridge，可能先碰到旧 bug
- `bin/vibe roadmap list --json` 当前对脏字符较敏感，实现时需避免进一步扩大 JSON 渲染风险

---

## Scope Guard

- **Phase 1 不涉及** flow gate、issue->flow 主链调整
- **Phase 1 不做** GitHub Project 原生依赖关系字段同步
- **Phase 1 不引入** task DAG 或自动调度
- **Phase 2 前置条件已满足**: #124 已通过 PR #143 完成，flow identity 主链已稳定

---

## 与历史文档的关系

### 保留的认知资产

- **roadmap-dependency-standard.md**: 核心依赖模型、ready/blocked 语义、merged PR 证据规则
- **依赖查询先行**: 先做查询层，后做 gate 的分阶段思路

### 不再采用的执行路径

- **gate-implementation.md (2026-03-11)**:
  - 包含 issue->flow 主链调整，已与 #124 重叠
  - 6 task 合并执行，未分阶段
  - **已被本文档替代**

- **worthiness-review.md (2026-03-12)**:
  - 审查结论：当前分支不值得继续（草稿混合、边界扩散）
  - **建议被采纳**: 本文按分阶段重新设计，先做查询层

---

## 验收标准

### Phase 1 验收

- [ ] `depends_on_item_ids` 字段已在标准中定义
- [ ] `ready/blocked/blockers` 查询能力已实现
- [ ] `roadmap status/show` 可见 blocker 信息
- [ ] 所有测试通过
- [ ] 不涉及 flow gate / issue->flow 主链调整

### Phase 2 验收（可开始规划）

- [ ] flow gate 逻辑已实现（flow new + flow bind issue 双入口）
- [ ] issue -> roadmap item 解析已集成
- [ ] 依赖门禁可阻止在 blocked item 上启动 flow
- [ ] 不提供跳过 gate 的软开关
- [ ] 所有测试通过
