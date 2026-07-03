# Contract: ADR Frontmatter (decides + scope)

**Feature**: 011-adr-recall | **Data model**: [data-model.md](../data-model.md)

本契约定义 ADR frontmatter 新增字段的 schema、写作规范与质量判据。是召回程序（第一步语义匹配、第二步代码匹配）与 ADR 作者共同遵守的数据契约。

---

## Schema（增量）

既有 frontmatter 字段不变。新增：

```yaml
---
document_type: decision
title: <决策标题>
adr_id: NNNN
status: proposed | accepted | superseded
date: YYYY-MM-DD
supersedes: null | ADR-NNNN
superseded_by: null | ADR-MMMM
related_docs:
  - <path/to/doc.md>
issues:
  - <issue-number>
# ===== 新增（本特性） =====
decides: <一句话，决策对象 + 约束，<120 字>
scope:
  - <repo-relative path glob>
  - <repo-relative path glob>
---
```

---

## `decides` 字段

**定义**: 用一句话陈述"**决策对象**"与"**约束**"，<120 字。

**写作规则**:
1. 必须含**决策对象**（被约束的实体/机制，如 `DomainEvent`、`service 层依赖注入`）。
2. 必须含**约束词**（`必须 / 禁止 / 仅 / 不得 / 仅由 / MUST / MUST NOT` 等指令性表达）。
3. <120 字（硬上限，超长说明在写正文而非摘要）。
4. 不复制正文 Decision 段——压缩为可扫描摘要。

**示例（✅ 合规）**:
```yaml
decides: "DomainEvent 禁止承担 flow 状态机判断；FlowEvent 仅作 flow-local 审计投影，由 DomainEvent 单向投影产生。"
decides: "依赖注入必须经 Protocol（BackendProtocol 等）；service 层禁止直接实例化 backend。"
```

**反例（❌ 低质，自检会标记）**:
```yaml
decides: "我们选了事件驱动。"          # 无对象、无约束
decides: "见正文 Decision 节。"        # 无信息量
decides: "经过权衡决定采用 Protocol 进行依赖注入以提升可测试性和灵活性..."  # 超长 + 无约束词 + 论证而非决策
```

---

## `scope` 字段

**定义**: 该 ADR 治理的**代码位置**，值为仓库相对路径 glob 列表，支持 `*`（单层）与 `**`（多层）。

**写作规则**:
1. 指向**代码**路径（`src/`, `lib/`, `bin/` 等），不是文档（文档走 `related_docs`）。
2. 覆盖该 ADR 决策直接约束的所有代码位置——召回靠它判代码相关性，漏标 = 假阴性。
3. **supersede 继承**：若本 ADR `supersedes ADR-NNNN`，`scope` 必须覆盖被取代者的全部 `scope`（否则召回标记 supersede_gap 腐烂）。

**glob 语法**:
- `src/vibe3/models/domain_events.py` — 精确文件
- `src/vibe3/domain/handlers/**` — 目录递归
- `src/vibe3/execution/*.py` — 单层通配

**示例（ADR-0004 回填）**:
```yaml
scope:
  - src/vibe3/models/domain_events.py
  - src/vibe3/models/flow.py
  - src/vibe3/domain/handlers/**
  - src/vibe3/runtime/**
```

**与既有字段的边界**（防职责重叠）:
| 字段 | 指向 | 用途 | 受众 |
|------|------|------|------|
| `related_docs` | 文档（standards/guides） | 权威文档索引 | 人读 |
| `How` 段链接 | 文档 + 具体代码文件 + 说明 | 实现入口与人读上下文 | 人读 |
| `scope`（新） | 代码 path glob | 召回代码匹配锚点 | 机器匹配 |

`scope` 形式化 `How` 段已零散存在的代码路径信号（ADR-0004 `How` 已指 `domain_events.py`/`flow.py`），使之可 glob 匹配；它不替代 `How` 的人读说明。

---

## 质量判据（召回自检消费）

召回程序在 S3（decides 质量自检）、S4（scope 健康自检）按以下规则标记，结果写入 artifact 的 `decides_quality_flags` / `scope_rot_flags`：

| 检查 | 规则 | 命中标记 |
|------|------|----------|
| decides 对象缺失 | 未识别出决策对象（无领域名词实体） | `decides_quality_flags: {issue: "missing_object"}` |
| decides 约束缺失 | 无指令性约束词 | `decides_quality_flags: {issue: "missing_constraint"}` |
| decides 超长 | >120 字 | `decides_quality_flags: {issue: "too_long"}` |
| scope 路径不存在 | glob 展开后命中 0 个现存路径 | `scope_rot_flags: {kind: "missing_path"}` |
| scope supersede 缺口 | successor 未覆盖 predecessor 的 scope | `scope_rot_flags: {kind: "supersede_gap"}` |

**重要**: 质量标记**不阻塞召回**，但必须反映在 artifact；reviewer 据此判断是否需先修 ADR 再放行 plan（SC-004 腐烂可见）。
