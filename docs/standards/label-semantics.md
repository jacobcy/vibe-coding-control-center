---
document_type: standard
title: Label Semantics
status: active
scope: governance-labels
authority:
  - priority-scale
  - roadmap-scale
  - legacy-mapping
maintainer: Vibe Team
created: 2026-06-01
last_updated: 2026-06-01
related_docs:
  - supervisor/roadmap-common.md
  - supervisor/governance/assignee-pool.md
  - supervisor/governance/roadmap-intake.md
---

# Label Semantics

本文档定义所有治理标签的语义，作为权威参考。

## Priority Scale (priority/[0-9])

`priority/[0-9]` 用于同一 roadmap 桶内的细粒度抢占顺序。

### 刻度定义

| Label | 语义 | 使用场景 |
|-------|------|----------|
| `priority/9` | 最高优先级 | 紧急、阻塞其他工作、需立即处理 |
| `priority/7-8` | 很高优先级 | 重要且紧急、近期需完成 |
| `priority/5-6` | 中等优先级 | 正常优先级、按计划推进 |
| `priority/3-4` | 较低优先级 | 可延后、非关键路径 |
| `priority/1-2` | 低优先级 | 可选增强、低价值 |
| `priority/0` | 最低优先级 | 默认值、可选增强、无紧迫性 |

**关键规则**：**数字越大优先级越高**。

### 默认值

- 无 `priority/[0-9]` 标签时，默认为 `priority/0`（最低优先级）
- 新 issue 若未指定优先级，按 `priority/0` 处理

### 与 roadmap/p0-p2 的关系

**注意**：`priority/[0-9]` 与 `roadmap/p0-p2` 语义**相反**，容易混淆：

- `priority/[0-9]`：**数字越大越紧急**（9 = 最高优先级）
- `roadmap/p0-p2`：**数字越小越紧急**（p0 = 当前版本，最紧急）

**记忆方法**：
- `priority`：类似"评分"，分数越高越重要
- `roadmap`：类似"版本号"，版本号越小越近

## Roadmap Scale (roadmap/p0-p2)

`roadmap/p0-p2` 用于表达版本目标优先级。

### 刻度定义

| Label | 语义 | 使用场景 |
|-------|------|----------|
| `roadmap/p0` | 当前版本目标 | 本版本必须完成、阻塞发布 |
| `roadmap/p1` | 下一版本目标 | 下版本计划、可延后 |
| `roadmap/p2` | 未来版本目标 | 未来计划、可选 |

**关键规则**：**数字越小越紧急**。

### 特殊 roadmap 标签

| Label | 语义 | 使用场景 |
|-------|------|----------|
| `roadmap/rfc` | 需要人类决策 | 架构方向未定、需要讨论 |
| `roadmap/epic` | 需要拆分 | 范围过大、需拆分为多个 sub-issues |

## Legacy Priority Labels

为兼容历史 issue，支持以下 legacy priority labels：

| Legacy Label | 映射到 | 语义 |
|--------------|--------|------|
| `priority/critical` | `priority/9` | 最高优先级 |
| `priority/high` | `priority/7` | 很高优先级 |
| `priority/medium` | `priority/5` | 中等优先级 |
| `priority/low` | `priority/3` | 较低优先级 |

**建议**：新 issue 统一使用数字 `priority/[0-9]`，避免使用 legacy labels。

## Implementation Notes

### 排序逻辑

在 ready queue 排序中，优先级判断顺序：

1. **Milestone**：大桶排序（v0.1 < v0.3）
2. **Roadmap**：同一 milestone 内按 `roadmap/p0-p2` 排序（p0 < p1 < p2）
3. **Priority**：同一 roadmap 内按 `priority/[0-9]` 排序（9 > 8 > ... > 0）
4. **Issue Number**：tie-break，按 issue 编号升序

### 代码实现

优先级解析函数位于 `src/vibe3/orchestra/queue_ordering.py`：

```python
def resolve_priority(labels: list[str]) -> int:
    """Resolve priority from labels.
    
    Returns:
        Priority value (0-9). Higher number = higher priority.
        Defaults to 0 if no priority label found.
    """
```

**关键**：代码实现已正确，`resolve_priority()` 返回值越高优先级越高。

### Governance LLM 引导

为避免 governance LLM 误读优先级：

1. `supervisor/governance/assignee-pool.md` 的 Queue Guidance 部分包含明确的优先级刻度表
2. 本文档作为权威参考，被 `supervisor/roadmap-common.md` 引用
3. Vibe-roadmap (Tier 3) 审查时可纠正 governance 的优先级误判

## Authority

本文档是优先级语义的权威定义：

- 所有治理材料应引用本文档，而不是重复定义
- 优先级判断冲突时，以本文档为准
- 本文档更新需经 team review
