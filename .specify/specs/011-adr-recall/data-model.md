# Data Model: ADR Context Recall

**Feature**: 011-adr-recall | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

本特性**无 Python 数据模型**（零 Python，FR-014）。数据形态为 markdown frontmatter + 内嵌 artifact。本文档定义这些结构的字段、校验与状态流转，供 skill 与 review 审计消费。

---

## Entity: ADR（frontmatter 扩展）

ADR 既有的 frontmatter 字段不变（`document_type, title, adr_id, status, date, supersedes, superseded_by, related_docs, issues`），**新增**两个召回刻面字段：

| 字段 | 类型 | 必填（accepted 起） | 说明 |
|------|------|---------------------|------|
| `decides` | string（一句话，<120 字） | 是 | 决策对象 + 约束。召回第一步语义匹配的扫描源。质量见 [contracts/adr-frontmatter.md](./contracts/adr-frontmatter.md) §质量判据 |
| `scope` | list[path glob] | 是 | 该 ADR 治理的代码位置（仓库相对路径，支持 `*`/`**`）。召回第二步代码匹配的锚点 |

**校验规则**:
- `status: accepted` 的 ADR 必须填 `decides` + `scope`（FR-002）。
- `status: proposed` 的 ADR 可暂缺（尚未结晶），但合入 accepted 前必须补全。
- `decides` 自检：须含决策对象 + 约束词；否则标低质（不阻塞，但 artifact 反映）。
- `scope` 自检：glob 展开须命中 ≥1 现存路径；supersede 链须覆盖被取代者 scope（见 [research.md §7](./research.md)）。

**状态流转**（既有，不变）:

```text
proposed -> accepted -> superseded
```

- `accepted` 起 `decides`/`scope` 必填。
- `superseded` ADR 的 `decides`/`scope` 保留（用于 supersede 继承检测 R2），但其 `scope` 治理权移交给 successor。
- ADR 正文一旦 accepted 不可重写；supersede 只更新 lifecycle metadata + `scope` 继承（既有约定，本特性不改变）。

---

## Entity: ADR-Consideration Artifact

召回产出物，内嵌于 plan.md 的 "ADR Consideration" 节。是一个**不可变快照**（绑定一次召回的基线），无状态流转。详细 schema 见 [contracts/artifact.md](./contracts/artifact.md)。

| 字段 | 类型 | 说明 |
|------|------|------|
| `adr_snapshot_baseline` | {branch, commit_sha} | 召回基线，防分支陈旧误判 |
| `evaluated_adrs` | list[adr_id] | 至少读了 `decides` 的全集（审计零匹配用） |
| `applicable` | list[{adr_id, summary}] | `scope` 命中且语义相关、读了 body 的 ADR |
| `dismissed` | list[{adr_id, reason}] | 评估后不适用的 ADR，**reason 必填** |
| `decides_quality_flags` | list[{adr_id, issue}] | `decides` 自检标记的低质项 |
| `scope_rot_flags` | list[{adr_id, kind, detail}] | `scope` 自检标记的腐烂项（kind = missing_path / supersede_gap） |
| `supersede_proposals` | list[{adr_id, new_adr_id, reason}] | plan 需偏离某 ADR 时的显式提议 |

**关系**:
- `evaluated_adrs` = `applicable` ∪ `dismissed`（accepted ADR 全集）。
- 任一 accepted ADR 必须出现在 `applicable` 或 `dismissed` 之一，否则 artifact 不完整 → review BLOCK。
- `decides_quality_flags` / `scope_rot_flags` 是横切标记，可指向 `applicable` 或 `dismissed` 中的 ADR。

---

## Entity: Recall Procedure（无状态行为契约）

召回是一个**无状态**的有序过程（不持久化中间态），每次调用从头执行。其"状态"是步骤进度，见行为契约 [contracts/recall-checklist.md](./contracts/recall-checklist.md)。步骤间的"状态流转"即 checklist 推进：

```text
S1 读 INDEX.decides 列(语义相关性)
  -> S2 改动文件(vibe3 inspect base) 匹配 scope(代码相关性)
  -> S3 decides 质量自检
  -> S4 scope 健康自检(路径存在 + supersede 继承)
  -> S5 读命中项 body
  -> S6 产 artifact(填 plan.md "ADR Consideration" 节)
```

每步的输入/输出/失败模式见 recall-checklist.md。无持久化实体，故无迁移、无并发问题。

---

## 与既有真源的关系（不重叠）

| 数据 | 真源 | 本特性是否触碰 |
|------|------|----------------|
| ADR lifecycle（status/supersede） | `docs/decisions/` frontmatter | 仅**新增** `decides`/`scope` 字段，不改 lifecycle 语义 |
| 改动文件清单 | `vibe3 inspect base`（既有） | **只读**消费，不改 |
| FailedGate / block-flow | `src/vibe3/orchestra/failed_gate.py`（既有） | **只读**消费（BLOCK 喂入），不改 |
| `roadmap/rfc` 标签语义 | `skills/vibe-roadmap`（既有） | **引用**语义，reviewer 建议打标，不改打标路径 |
| plan.md 结构 | plan-template（既有） | **新增** "ADR Consideration" 节，不改既有节 |

本特性净增数据实体仅 2 个（`decides`/`scope` 字段 + artifact），均为 markdown，无数据库、无 ORM、无新 Python model。
