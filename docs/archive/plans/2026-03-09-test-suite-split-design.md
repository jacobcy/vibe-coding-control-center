# Test Suite Split Design

- 日期: 2026-03-09
- 状态: approved
- 主题: 按 `lib/flow*`、`lib/roadmap*` 的职责边界拆分超重 bats 文件

## Goal

- 将 `tests/test_flow.bats` 与 `tests/test_roadmap.bats` 拆成更小、更聚焦的测试文件。
- 保持现有测试语义、断言内容与运行结果不变。
- 让测试文件分组与 `lib/flow*`、`lib/roadmap*` 的模块边界更接近。

## Non-Goals

- 不改动 `lib/flow*.sh` 与 `lib/roadmap*.sh` 的生产逻辑。
- 不借机重写断言风格、编号或测试策略。
- 不批量修订历史 plan/design 文档里的旧测试路径引用。

## Context

- 当前 `tests/test_flow.bats` 约 1080 行，覆盖 `flow help/runtime/lifecycle/bind/done/pr/review` 多个主题。
- 当前 `tests/test_roadmap.bats` 约 473 行，覆盖 `status/query/render/write/audit` 多个主题。
- 两个文件都已经天然按主题顺序排列，适合“原样搬迁 + 共享 helper 抽取”。

## Options

### Option A: 严格按库文件一一拆分

优点：
- 模块映射最强

代价：
- 文件数量过多
- `flow_help/show/status/list` 这类小模块会导致测试文件过碎

### Option B: 保留现状，只做 helper 抽取

优点：
- 改动最小

代价：
- 超重问题没有真正解决
- 后续继续扩展时冲突面仍然大

### Option C: 混合拆分（已选）

优点：
- 保持和库边界的大致对应关系
- 文件数量适中，迁移成本低
- 便于按主题定向运行 bats

代价：
- 不是每个 `lib/*` 文件都能做到一一映射

## Approved Design

### Flow

- 抽取共享 helper：`tests/helpers/flow_common.bash`
- 新增 4 个测试文件：
  - `tests/flow/test_flow_help_runtime.bats`
  - `tests/flow/test_flow_lifecycle.bats`
  - `tests/flow/test_flow_bind_done.bats`
  - `tests/flow/test_flow_pr_review.bats`

### Roadmap

- 抽取共享 helper：`tests/helpers/roadmap_common.bash`
- 新增 3 个测试文件：
  - `tests/roadmap/test_roadmap_status_render.bats`
  - `tests/roadmap/test_roadmap_query.bats`
  - `tests/roadmap/test_roadmap_write_audit.bats`

### Migration Rules

- 原测试块按主题原样搬运，不重写逻辑。
- `setup()` 与 fixture helper 统一下沉到 `tests/helpers/`。
- 迁移完成后删除原始超重文件，避免双维护。

## Verification

```bash
bats tests/flow/*.bats
bats tests/roadmap/*.bats
bats tests/flow/*.bats tests/roadmap/*.bats
```

## Expected Result

- Flow 和 roadmap 测试被拆成更小的可维护单元。
- 原断言覆盖率与运行结果保持一致。
- 后续修改 `lib/flow*` 或 `lib/roadmap*` 时，能更直接命中对应测试文件。