# Roadmap List Color Design

- 日期: 2026-03-09
- 状态: approved
- 主题: `vibe roadmap list` 分组标题着色

## Goal

- 为 `vibe roadmap list` 的分组标题增加颜色提示，提升与 `vibe flow list` 的视觉一致性。
- 保持当前分组结构、文本顺序和 `--json` 行为不变。

## Non-Goals

- 不新增命令参数。
- 不改动 `roadmap status/show/audit` 的输出。
- 不给标题正文、ID、描述加额外颜色层级。

## Context

- `lib/roadmap_query.sh` 已有 `_vibe_roadmap_supports_color`、`_vibe_roadmap_format`、`_vibe_roadmap_color_status`。
- 当前 `roadmap list` 已按状态分组，但分组标题仍是纯文本。
- `vibe flow list` 的视觉参考是：
  - 用彩色标题做一级分组提示
  - 用有限颜色突出状态，而不是整屏上色
  - 非 TTY 输出保持纯文本

## Options

### Option A: 只给分组标题上色（推荐）

- `P0` 红色加粗
- `Current` 绿色加粗
- `Next` 蓝色加粗
- `Deferred` 黄色加粗
- `Rejected` 灰色加粗
- 计数 `(n)` 与标签同色

优点：
- 与 `vibe flow list` 的“少量关键色”风格一致
- 不影响正文可读性
- 对现有测试和非 TTY 兼容性影响最小

代价：
- 视觉增强仅集中在分组层，组内 item 仍较朴素

### Option B: 分组标题和 item ID 都着色

优点：
- 扫描 ID 更快

代价：
- 噪音更高
- 长列表下容易显得花

### Option C: 恢复旧式 `[status]` 行内着色

优点：
- 单条 item 状态更直接

代价：
- 与新的分组布局重复表达状态
- 不如分组标题上色干净

## Approved Design

- 采用 Option A。
- 仅在 `_vibe_roadmap_supports_color` 为真时输出 ANSI 颜色。
- 分组标题文本格式保持：
  - `P0 (3)`
  - `Current (7)`
- 颜色映射直接复用现有 roadmap 状态配色语义，不新建第二套配色规则。
- 非 TTY 输出继续保持无 ANSI 转义，现有文本测试语义不变。

## Files To Modify

- `lib/roadmap_query.sh`
- `tests/test_roadmap.bats`

## Verification

```bash
bats tests/test_roadmap.bats
bin/vibe roadmap list
```

## Expected Result

- 交互终端下，`roadmap list` 的分组标题有颜色。
- bats 中非 TTY 断言继续不包含 ANSI。
- 默认文本结构不变化，只增加交互态颜色。
