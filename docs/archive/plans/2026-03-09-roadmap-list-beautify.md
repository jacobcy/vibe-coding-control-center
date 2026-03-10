# Roadmap List Beautify Plan

- 日期: 2026-03-09
- 状态: discussion
- 主题: `vibe roadmap list` 文本输出美化

## Goal

- 优化 `vibe roadmap list` 的终端文本输出，使 roadmap item 在数量增多时仍然易扫读、易定位。
- 保持现有命令语义不变，只调整默认文本渲染。

## Non-Goals

- 不修改 `--json` 输出结构。
- 不新增 roadmap 数据字段。
- 不改动 `roadmap add/show/status/audit` 的行为。
- 不处理与当前请求无关的 `flow`、`task`、`issue` 逻辑。

## Tech Stack

- Zsh CLI: `bin/vibe`
- Shell 实现: `lib/roadmap_query.sh`
- 测试: `tests/test_roadmap.bats`

## Current State

- 当前输出为单行列表，格式接近：
  - `[current] gh-34         feat(task sync): ...`
- 优点：紧凑、兼容现有使用方式。
- 问题：条目较多时视觉分层弱，状态分组与重点项不够突出。

## Candidate Approaches

### Option A: 分组列表（推荐）

- 按状态分组输出，如 `P0 (3)`、`Current (5)`、`Next (4)`。
- 每组内保留单行 item，继续使用 `id + title` 形式。
- 对齐列宽，组间留空行。

优点：
- 保持紧凑，不破坏终端阅读节奏。
- 最接近当前实现，测试改动最小。
- 对大量 item 的可扫读性最好。

代价：
- 输出顺序从“全量平铺”变为“按状态分段”。

### Option B: 表格列表

- 增加表头：`STATUS  ID  TITLE`
- 每个 item 占一行，统一列宽。

优点：
- 结构明确。

代价：
- 中文长标题下表格容易错位。
- 终端窄宽时观感一般。

### Option C: 卡片式多行列表

- 每个 item 输出为 2-3 行，附带 `source` / `linked_task_ids` 等信息。

优点：
- 信息密度高。

代价：
- 明显变长，不适合作为 `list` 默认输出。

## Recommended Design

- 采用 Option A。
- 默认文本输出改为“按状态分组 + 组标题计数 + 组内单行 item”。
- `title == roadmap_item_id` 时继续去重，避免重复显示。
- 无匹配项时继续输出 `No roadmap items found.`。

## Planned Tasks

1. 在 `lib/roadmap_query.sh` 重构文本渲染，仅调整 `list` 默认文本分组与排版。
2. 保持 `--json`、过滤参数和空结果逻辑不变。
3. 在 `tests/test_roadmap.bats` 增加/更新文本输出断言。
4. 运行 roadmap 相关测试，验证输出稳定。

## Files To Modify

- `lib/roadmap_query.sh`
- `tests/test_roadmap.bats`

## Test Command

```bash
bats tests/test_roadmap.bats
```

## Expected Result

- `vibe roadmap list` 默认文本输出出现状态分组标题。
- 每组条目保持单行、对齐稳定。
- `bats tests/test_roadmap.bats` 通过。

## Estimated Change Summary

- 新增: 0-1 个渲染 helper，约 20-35 行
- 修改: `list` 文本输出逻辑，约 15-30 行
- 测试: 调整/新增 15-30 行
