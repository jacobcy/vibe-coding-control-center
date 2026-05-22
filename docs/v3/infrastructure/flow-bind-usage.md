# Flow Bind 使用指南

## 概述

`flow bind` 命令用于建立 flow 与 issue 之间的关联关系，支持三种角色：
- `task`: 表示该 flow 对应的 task issue
- `related`: 表示相关联的 issue（不阻塞）
- `dependency`: 表示依赖的 issue（阻塞当前 flow）

## 基本用法

```bash
# 绑定 task issue
vibe3 flow bind --role task <issue-number>

# 绑定相关 issue
vibe3 flow bind --role related <issue-number>

# 绑定依赖 issue
vibe3 flow bind --role dependency <issue-number>
```

## 多依赖语义（重要）

### 行为描述

当使用 `flow bind --role dependency A B C` 绑定多个依赖时：

1. **按顺序调用**: 对每个依赖 issue 按顺序调用 `block_flow()`（A → B → C）
2. **数据库字段**: flow state 的 `blocked_by_issue` 字段被最后一次调用覆盖，最终值为 C
3. **Issue Body 累积**: 所有依赖都会累积到 issue body 的 `blocked_by` 列表中（A, B, C 都会保留）
4. **链接记录**: 所有依赖都记录在 `flow_issue_links` 表中，角色为 `dependency`

### 示例

```bash
# 绑定多个依赖
vibe3 flow bind --role dependency 100 101 102
```

执行后：
- Flow state 表: `blocked_by_issue = 102`（最后一个）
- Issue body 的 blocked_by 字段: `[100, 101, 102]`（全部累积）
- Flow issue links 表: 三条记录，issue_number 分别为 100, 101, 102

### 实现细节

这种"双重语义"源于两层存储机制：
- **Flow State 表**: 单值字段 `blocked_by_issue`，每次 `block_flow()` 调用都会覆盖
- **Issue Body**: 列表字段 `blocked_by`，通过 `_project_blocked_state()` 方法合并去重

代码位置：`src/vibe3/commands/flow_manage.py:310-320`

## 最佳实践

### 避免同时绑定多个依赖

由于多依赖语义的复杂性，建议：

**不推荐**:
```bash
vibe3 flow bind --role dependency 100 101 102
```

**推荐**:
```bash
# 逐个绑定，明确主依赖
vibe3 flow bind --role dependency 100
vibe3 flow bind --role dependency 101
vibe3 flow bind --role dependency 102
```

或使用 `vibe3 flow blocked --task <issue>` 命令逐个建立依赖关系。

### 使用场景区分

- **Task**: 每个 flow 只有一个 task issue
- **Related**: 可绑定多个相关 issue
- **Dependency**: 建议绑定主依赖 issue，避免多依赖混淆

## 参考文档

- 命令标准: `docs/standards/v3/command-standard.md` (flow bind 章节)
- 依赖管理: `docs/references/flow-dependency.md`
- 代码实现: `src/vibe3/commands/flow_manage.py`
